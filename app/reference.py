"""Static study guides. Game facts and assistant interpretations stay distinct."""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import re

from app.catalog import canonical_hero_ids, get_catalog, index


def item_reason(item: dict, hero: dict | None = None) -> dict:
    text = item['description'] + item['stats']
    reasons = []
    if '法力' in text:
        reasons.append('改善技能启动或释放频率；先看英雄法力上限和技能价值。')
    if '攻击速度' in text or '每次攻击' in text:
        reasons.append('服务于普攻、攻击触发效果或持续输出；需要前排争取输出时间。')
    if '重伤' in text:
        reasons.append('用于压制治疗；若英雄技能自带重伤，先判断覆盖是否已经足够。')
    if '击碎' in text or '护甲削减' in text:
        reasons.append('降低敌方防御，帮助对应伤害类型的队友输出；不默认把同类减抗重复相加。')
    if any(x in item['stats'] for x in ('护甲', '魔抗', '魔法抗性', '生命上限', '生命值')) or any(x in item['description'] for x in ('获得一个护盾', '获得护盾', '伤害减免')):
        reasons.append('提高生存或承伤能力；物理压力看护甲，法术压力看魔抗，混合压力看综合防御。')
    if '技能暴击' in text:
        reasons.append('让技能获得暴击收益；已有同类效果时，要比较额外暴击收益与其他装备的机会成本。')
    if '全能' in text or ('治疗' in item['description'] and '重伤' not in item['description']) or re.search(r'(?:回复|恢复).{0,8}生命', text):
        reasons.append('提供续航；适合能持续参与战斗的单位，不能代替足够的基础伤害和承伤。')
    if not reasons:
        reasons.append('依据实际装备效果与该阵容的职责搭配，不能只凭装备名称判断强弱。')
    if hero and '重伤' in hero['skill_description'] and '重伤' in text:
        reasons.insert(0, f"{hero['name']}的技能已经包含重伤，先考虑是否需要扩大覆盖范围。")
    return {'item_id': item['id'], 'reasons': reasons[:3], 'evidence_type': 'assistant_analysis', 'source_id': item['source_id']}


def _hero_reference(hero: dict, data: dict, canonical: dict, items: dict) -> dict:
    matches = []
    builds, seen = [], set()
    front = back = carry = 0
    item_counts = Counter()
    for lineup in data['lineups']:
        for unit in lineup['units']:
            if canonical[unit['hero_id']] != canonical[hero['id']]:
                continue
            front += unit['row'] <= 2
            back += unit['row'] > 2
            carry += unit['carry']
            matches.append({'lineup_id': lineup['id'], 'name': lineup['name'], 'carry': unit['carry'], 'form_name': index(data['heroes'])[unit['hero_id']]['name']})
            signature = tuple(sorted(unit['item_ids']))
            if signature and signature not in seen:
                seen.add(signature)
                builds.append({'item_ids': unit['item_ids'], 'lineup_id': lineup['id'], 'lineup_name': lineup['name'], 'carry': unit['carry'],
                               'form_name': matches[-1]['form_name'], 'source_url': lineup['source_url']})
                item_counts.update(set(unit['item_ids']))
    skill = hero['skill_description']
    if hero['summon']:
        role = '召唤物 / 变身形态'
    elif carry:
        role = '后排输出' if hero['stats']['range'] >= 3 else '近战输出'
    elif front > back:
        role = '前排承伤 / 功能'
    else:
        role = '后排功能 / 过渡'
    damage = ('物理伤害' in skill, '魔法伤害' in skill, '真实伤害' in skill)
    damage_labels = [name for active, name in zip(damage, ('物理', '魔法', '真实')) if active]
    utilities = [label for keyword, label in (('重伤', '技能自带重伤'), ('护甲击碎', '技能自带减甲'), ('魔抗击碎', '技能自带减魔抗'),
                  ('晕眩', '控制'), ('治疗', '治疗'), ('护盾', '护盾')) if keyword in skill]
    principles = ['先理解技能的伤害类型和触发方式，再决定装备；面板攻击力不是英雄全部输出。']
    if '前排' in role:
        principles += ['优先让关键承伤单位活过第一轮集火；按对手物理或法术压力选择护甲与魔抗。', '能开出关键技能的防装通常比单纯堆一项面板更有意义；注意护盾、治疗与减伤的配合。']
    elif '近战' in role:
        principles += ['近战输出要兼顾伤害、续航与生存；只做伤害装可能来不及启动。', '观察技能是否突进、变身或需要叠层，避免让核心第一时间承受全部火力。']
    else:
        principles += ['普攻触发或持续叠层单位重视攻速与输出时间；技能型单位重视启动、法力循环和技能收益。', '前排不足时，继续给后排补第三件输出装未必是整队的最大提升。']
    if hero['name'] == '巴德':
        principles[1] = '木灵附着于攻击，攻速能增加技能持续期间的攻击机会；双攻速路线也依赖前排撑住战斗。'
    if hero['name'] == '辛德拉':
        principles[1] = '每次施放会增加蝴蝶，法力循环会影响后续技能收益；仍需前排保证持续施法。'
    return {'hero_id': hero['id'], 'role': role, 'role_basis': '根据官网阵容中的站位与主C标记归纳，专属强化可能改变职责。',
            'damage_type': ' / '.join(damage_labels) if damage_labels else '辅助 / 召唤 / 未单列', 'utility_tags': utilities,
            'equipment_principles': principles, 'builds': sorted(builds, key=lambda b: not b['carry']),
            'common_items': [{'item_id': i, 'build_count': count, **item_reason(items[i], hero)} for i, count in item_counts.most_common(8)],
            'lineups': list({m['lineup_id']: m for m in matches}.values()), 'evidence_type': 'assistant_analysis'}


def _lineup_profile(lineup: dict, heroes: dict, items: dict) -> dict:
    carry = heroes[lineup['carry_ids'][0]]
    cost = carry['cost']
    is_endgame = any(x in lineup['name'] for x in ('九五', '95'))
    fortune = '吉星' in lineup['name']
    roll_level = 9 if is_endgame and cost == 5 else {0: 8, 1: 5, 2: 6, 3: 7, 4: 8, 5: 9}[cost]
    style = '高人口运营' if is_endgame or cost >= 4 else f'{cost}费追星'
    gates = lineup['required_augment_ids']
    if gates:
        style = '专属强化构筑'
    entering = [f"自然来牌偏向{carry['name']}及前排搭档，而不是开局就强行搜这套。", '核心输出与前排装备能同时分配，散件不需要全部等待完美三件套。']
    avoiding = ['主C有较多同行且自己张数落后时，先考虑共享装备的其他路线。', '血量不足以支撑目标成型过程，或缺少关键转职／专属强化时，不照搬最终站位。']
    if cost <= 3 and not is_endgame:
        entering.append(f'已经有一定数量的低费主C与体系牌，能接受在{roll_level}人口阶段停留追星。')
        timing = [
            {'phase': '前期', 'condition': '来牌与散件初步吻合时', 'action': '用已有两星和合理前后排过渡，保留关键体系对子，不为最终羁绊牺牲即时战力。'},
            {'phase': f'{roll_level}人口搜牌窗口', 'condition': '主C张数领先、血量稳定、同行不多时', 'action': '在这一常见搜牌等级附近追关键三星；稳定时保留经济，持续大幅掉血时先补二星和防装。'},
            {'phase': '追星之后', 'condition': '主C与主坦达到阶段目标时', 'action': f"停止无目标刷新，再升人口补控制与辅助，最终参考{lineup['target_level']}人口站位。"},
        ]
    else:
        entering.append('有能稳定过渡的棋盘与经济，能够承担上人口后再找高费核心的成本。')
        timing = [
            {'phase': '前中期过渡', 'condition': '尚未拿到高费主C时', 'action': '让已两星的同类输出持有通用装备，前排先成型；不要为了等目标英雄把装备全放备战席。'},
            {'phase': '常见4阶段转换', 'condition': '升级后仍有搜牌预算、旧棋盘开始吃力时', 'action': '通常在8人口附近寻找四费核心与前排二星；4-1或4-2是参考窗口，不是每局必须照做的时刻。'},
            {'phase': '后期提升', 'condition': '中期关键二星能稳定战斗且经济允许时', 'action': '再考虑9人口高费拼图、控制与针对性站位；不能用最终九五站位倒推开局必须卖牌攒钱。'},
        ]
    if fortune:
        entering = ['先理解返场吉星可自选收菜回合的规则，再评估血量与失败预算。', '有能在收菜后接住装备与经济的过渡棋盘，且可以接受较高运营难度。']
        avoiding.insert(0, '不清楚还能承受几次失败，或已经没有转换战力的时间时，不为更大奖励硬拖。')
        style = '高风险经济运营'
    prerequisites = []
    if gates:
        prerequisites.append({'kind': 'augment', 'ids': gates, 'text': '依赖对应英雄专属强化；普通版本的英雄不能直接照搬此构筑。'})
        entering.insert(0, '已经获得对应专属强化，并确认装备与英雄张数能围绕它展开。')
    if lineup['emblem_ids']:
        prerequisites.append({'kind': 'emblem', 'ids': lineup['emblem_ids'], 'text': '官网最终站位使用纹章；没有纹章时要降低目标羁绊档位或调整成员。'})
    for name in lineup.get('unavailable_requirements', []):
        prerequisites.append({'kind': 'unverified', 'ids': [], 'text': f'原攻略依赖{name}，当前官网符文库未收录；此条仅作历史参考。'})
    core_units = sorted((u for u in lineup['units'] if u['item_ids']), key=lambda u: (not u['carry'], -len(u['item_ids'])))
    equipment = [{'hero_id': u['hero_id'], 'role': '官网主C标记' if u['carry'] else '前排 / 副C / 功能位',
                  'items': [item_reason(items[i], heroes[u['hero_id']]) for i in u['item_ids']]} for u in core_units]
    unique_name_notes = {
        '2244': '巴德通过攻击投掷木灵，塔姆等前排为其争取持续输出时间；攻速装与前排装需要同步考虑。',
        '2202': '艾希的物理持续输出与法系单位可以互补；前排存活时间会影响后排打出多少轮攻击与技能。',
        '2290': '纳尔需要攻击或受击积累收益，低费追星的张数优势与近战生存同样重要。',
        '4897': '辛德拉持续施法会增加蝴蝶，前排保护与技能循环共同影响后续输出。',
        '2311': '婕拉技能自带重伤。选择额外重伤装备前，先看队伍需要的是扩大覆盖还是补其他功能。',
        '2233': '缥缈之刃改变慎的射程和技能收益，属于获得专属强化后才成立的输出路线。',
        '2286': '急落怒放强化妮蔻的治疗、猛击与技能范围，装备需要同时考虑法术收益和生存。',
    }
    return {'lineup_id': lineup['id'], 'style_label': style, 'roll_level': roll_level, 'final_level': lineup['target_level'],
            'route_type': 'special' if gates else 'level' if is_endgame or cost >= 4 else 'reroll',
            'roll_level_note': '常见运营经验归纳，不是商店概率表或每局固定指令。',
            'difficulty': '较高' if fortune or is_endgame or lineup['emblem_ids'] else '中等',
            'win_condition': unique_name_notes.get(lineup['id'], f"围绕{carry['name']}的技能特点分配输出装备，用前排、控制与羁绊保证核心完成战斗任务。"),
            'choose_when': entering, 'avoid_when': avoiding, 'milestones': timing, 'prerequisites': prerequisites,
            'equipment': equipment, 'transition_principles': ['先保留通用的前排和同类输出打工单位，核心接装后再换下打工位。', '转阵优先看已做成装能否复用；不能只看下一套阵容的最终强度描述。'],
            'source_url': lineup['source_url'], 'evidence_type': 'assistant_analysis',
            'notes': ['官网站位与原文攻略是事实来源；适用条件、等级窗口与装备作用是学习用的归纳。'] +
                     (['官网标题与主C标记存在差异，阅读时应结合成员、装备和运营原文核对。'] if lineup['id'] == '2310' else [])}


def _augment_class(augment: dict, data: dict) -> tuple[str, list[str]]:
    name, desc = augment['name'], augment['description']
    cautions = []
    if '不具有任何已激活' in desc:
        return '特殊构筑', ['要求不激活相应特质／职业，不能直接套用以成型羁绊为核心的阵容表。']
    if '不能再购买经验值' in desc:
        return '特殊构筑', ['改变经验获取方式，需要重算刷新与升级节奏；不能照搬普通拉人口时间表。']
    if '相同英雄的2个' in desc:
        cautions.append('要求同名双单位上场，需要额外位置与追星安排；普通单份英雄站位不能直接照抄。')
    if '备战席没有任何英雄' in desc:
        cautions.append('需要维持空备战席，与长期囤对子追三星存在冲突。')
    if any(token in desc for token in ('你最强大的那个', '你最强大的【')):
        return '英雄专属', ['会改变指定英雄的玩法；优先核对英雄张数、出装和专属条件。']
    if any(t['name'] in name for t in data['traits']) and any(t in name for t in ('之徽', '之冕', '之心')):
        return '羁绊转职', ['纹章用于跨越有效羁绊档位；不要只因为拿到纹章就强行追最高档。']
    if any(x in name for x in ('街区', '门票', '刷新', '值得等待', '羽量级')):
        if '值得等待' in name:
            cautions.append('奖励英雄随机；只有随机到的指定英雄适合该构筑时，才有追星价值，不能当作任意英雄复制器。')
        return '搜牌追星', cautions + ['低费追星也要检查同行与自己张数，不代表拿到符文就必须赌某一张牌。']
    if any(x in name for x in ('对冲基金', '利滚利', '低利率', '预算', '头脑', '升级', '新人入队', '大买特买', '高端购物', '天降金币', '前瞻思维', '遥遥领先', '金色追求')):
        if '不再获得利息' in desc:
            cautions.append('不再获得利息，普通的存息规则在此不成立。')
        return '经济与经验', cautions + ['经济收益需要有兑现时间；已经承受不起下一轮失败时，不能用未来收益替代当前战力。']
    if any(x in name for x in ('装备', '锻炉', '锻造', '百宝袋', '潘朵拉', '打捞', '重铸', '拆卸', '锅铲', '神器')):
        return '装备资源', cautions + ['根据已有装备缺口选择，额外资源不等于自动解决输出与前排分配。']
    if any(x in desc for x in ('治疗效果', '护盾值', '伤害减免', '魔法抗性', '护甲')):
        return '承伤续航', cautions
    return '输出与通用战力', cautions


def _pair_reason(augment: dict, lineup: dict, heroes: dict, profile: dict, category: str) -> str:
    """Explain a published pairing without treating its source rank as statistics."""
    name, desc = augment['name'], augment['description']
    core = heroes[lineup['carry_ids'][0]]['name']
    if '急落怒放' in name:
        return '提升妮蔻的技能治疗、猛击和范围，让她有作为核心的条件；需要追星、法术收益与生存共同支撑。'
    if '缥缈之刃' in name:
        return '额外射程和技能伤害改变慎的输出方式，是这条专属输出路线的前置条件；站位与装备也要随之改变。'
    if category == '羁绊转职':
        return '纹章帮助最终站位跨越羁绊档位或腾出一个位置；先看装备页的纹章持有者与目标档位，没有对应核心牌时仍不强冲。'
    if '次级英雄复制器' in desc:
        return f'复制器只支持3费或以下弈子，可在接近三星时补{core}或低费关键搭档；先留好目标牌，不能复制四、五费核心。'
    if '羽量级' in name:
        return f'攻速收益只覆盖1费、2费弈子；重点看{core}和低费搭档是否在适用范围，不能把加成计给高费替换位。'
    if any(t in name for t in ('街区', '门票', '常客优惠')):
        return f'额外刷新或刷新折扣能帮助寻找{core}与体系对子；在计划的搜牌等级兑现，达到二星／三星阶段目标后再升人口。'
    if '投资回报' in name:
        return '完成规定刷新次数后才得到冠冕；追星过程能推进奖励，但不应为凑次数浪费经济，且奖励不能提前当作可用人口。'
    if '打气' in name:
        return f'攻速随回合累积，有利于{core}及副C的持续攻击；较早拿到有更多成长时间，也需要前排延长输出窗口。'
    if '明智消费' in name:
        return '花金币刷新会提供经验，同时禁止直接购买经验；搜牌与升级绑在一起，必须按实际等级重算节奏。'
    if '高端购物' in name:
        return '商店按高一级的概率刷新，有利于寻找高费核心；只改变商店概率，既不直接增加等级也不保证找到目标。'
    if '纷乱头脑' in name:
        return '满备战席是额外经验的前提；高人口路线可用它推进升级，但需要为凑满备战席占用的金币留预算。'
    if '利滚利' in name:
        return '提高存款可获得的利息上限，适合有过渡战力和兑现时间的运营局；大掉血时仍要先花钱补战力。'
    if '耐心学习' in name:
        return '玩家战斗后获得经验，帮助运营路线推进人口；收益随回合兑现，不能立即替代当轮二星质量。'
    if any(t in name for t in ('锻炉', '光明圣物')):
        return '根据实际出现的神器／光明装备选持有者；随机候选不保证出现目标神装，延后领取的奖励还需要能存活到兑现。'
    if '潘朵拉' in name:
        return '备战席装备每回合随机变化，可修正散件方向；要保留已确定给核心的装备，等待变装也有损失战力的代价。'
    if '打捞桶' in name:
        return '出售持有者可以拆回散件，有助于从打工装转向核心装备；纹章、冠冕等例外以符文描述为准。'
    if '理想主义' in name:
        return '提升正义之手持有者的伤害，适合把装备交给能持续输出并利用续航的单位；增伤并非全队无条件生效。'
    if '联合抵抗' in name:
        return '同排达到指定人数才获得双抗；可强化前排承伤，但要同时考虑对手范围技能，不能只为触发条件无脑扎堆。'
    if '魔杖' in name:
        return f'补充大棒与法术加成，服务于技能有法术收益的核心或副C；先核对{core}技能中的加成类型与当前装备缺口。'
    named_traits = [t['name'] for t in lineup['traits'] if t['name'] in desc]
    if named_traits:
        return f"效果明确作用于{'、'.join(named_traits)}体系中的单位；先核对阵容里哪些棋子实际受益，并按描述安排触发条件和站位。"
    if '治疗' in desc or '全能汲取' in desc:
        return '续航能让承伤或近战输出多完成几轮攻击与技能；要同时具备足够伤害与基础防御，治疗触发范围和对象以描述为准。'
    if '护盾' in desc:
        return '通过护盾为关键单位争取战斗时间；先确认触发对象与距离，不能把需要友军倒下的收益当成开战即有的防御。'
    if category == '装备资源':
        return '补充核心和前排的装备缺口，适合多持有者分装；随机资源不能按指定装备预支，后续奖励要评估兑现时间。'
    return f'官网将它列入此构筑的选择范围；结合{core}与前排的缺口判断收益，效果中的指定费用、对象和兑现时间必须满足。'


@lru_cache(maxsize=1)
def get_reference() -> dict:
    data = get_catalog()
    heroes, items, augments = (index(data[k]) for k in ('heroes', 'items', 'augments'))
    canonical = canonical_hero_ids(data)
    hero_studies = {h['id']: _hero_reference(h, data, canonical, items) for h in data['heroes']}
    profiles = {l['id']: _lineup_profile(l, heroes, items) for l in data['lineups']}
    relations = []
    augment_studies = {}
    for augment in data['augments']:
        category, cautions = _augment_class(augment, data)
        entry = {'augment_id': augment['id'], 'category': category, 'cautions': cautions, 'lineups': []}
        for lineup in data['lineups']:
            aid = augment['id']
            if aid in lineup['augment_ids']:
                relation = {'basis': 'official_primary', 'label': '官网优选', 'reason': _pair_reason(augment, lineup, heroes, profiles[lineup['id']], category), 'weight': 3}
            elif aid in lineup['alternate_augment_ids']:
                relation = {'basis': 'official_alternate', 'label': '官网备选', 'reason': _pair_reason(augment, lineup, heroes, profiles[lineup['id']], category), 'weight': 2}
            else:
                named_traits = [t for t in lineup['traits'] if t['name'] in augment['name']]
                if aid in lineup['required_augment_ids']:
                    relation = {'basis': 'mechanic_inference', 'label': '专属条件适配', 'reason': _pair_reason(augment, lineup, heroes, profiles[lineup['id']], category), 'weight': 1}
                elif category == '羁绊转职' and named_traits:
                    relation = {'basis': 'mechanic_inference', 'label': '羁绊机制参考', 'reason': f"{named_traits[0]['name']}与阵容方向一致，需确认纹章能否跨越有效档位。", 'weight': 1}
                elif category == '搜牌追星' and profiles[lineup['id']]['route_type'] in ('reroll', 'special') and '值得等待' not in augment['name']:
                    core_cost = heroes[lineup['carry_ids'][0]]['cost']
                    if '羽量级' in augment['name'] and core_cost > 2:
                        continue
                    relation = {'basis': 'mechanic_inference', 'label': '追星思路参考', 'reason': '仅1费和2费弈子获得此攻速收益；本阵容的低费核心在适用范围内，仍需检查前排与追星条件。' if '羽量级' in augment['name'] else '额外刷新机会有助于寻找核心与体系对子；先确定预算与张数优势，再选择追星路线。', 'weight': 1}
                elif category == '经济与经验' and lineup['style'] == 'level' and not any('冲突' in c for c in cautions):
                    relation = {'basis': 'mechanic_inference', 'label': '运营思路参考', 'reason': '高人口路线需要经济或经验兑现时间；先有能过渡的棋盘，再考虑未来收益。', 'weight': 1}
                elif category == '装备资源' and (lineup['emblem_ids'] or len(set(i for u in lineup['units'] for i in u['item_ids'])) >= 5):
                    relation = {'basis': 'mechanic_inference', 'label': '装备缺口参考', 'reason': '阵容有多个装备持有者或转职需求，可根据具体资源效果补缺；不能把随机奖励视为指定装备。', 'weight': 1}
                else:
                    continue
            row = {'augment_id': aid, 'lineup_id': lineup['id'], 'reason_evidence_type': 'assistant_analysis', **relation}
            relations.append(row)
            entry['lineups'].append(row)
        entry['lineups'].sort(key=lambda r: -r['weight'])
        augment_studies[augment['id']] = entry
    for lineup in data['lineups']:
        profiles[lineup['id']]['augment_matches'] = sorted([r for r in relations if r['lineup_id'] == lineup['id']], key=lambda r: -r['weight'])
    return {'version': data['meta']['version'], 'season': data['meta']['season'],
            'note': '这是赛前和赛后查阅的学习手册，不要求实时输入对局状态。分析建议与官网原文分别标记。',
            'heroes': hero_studies, 'lineups': profiles, 'augments': augment_studies,
            'fundamentals': [
                {'title': '什么时候搜牌', 'if': '主C与前排有对子、棋盘开始承受不起掉血，或正处于计划中的追星等级时。', 'then': '先定义这轮目标与预算：补二星、找关键羁绊还是追三星。达成阶段目标就停，不因为没见到某张牌无限刷新。'},
                {'title': '什么时候升级', 'if': '已有棋盘能过渡、升级能增加有效战力，且升级后仍留有兑现新等级的搜牌预算时。', 'then': '比较多上一人、改善商店与直接搜二星的收益。稳定才考虑拉高上限，不能把“某回合上八”当作固定作业。'},
                {'title': '什么时候合装备', 'if': '装备能让关键前排活得更久、让打工C稳定换怪，或能扩大连胜收益时。', 'then': '优先完成有明确持有者的通用装备。稳定局可以短等补充信息；持续大掉血时，不为三件完美神装空置所有散件。'},
                {'title': '什么时候换路线', 'if': '核心同行多、自己张数落后、关键条件缺失，或成装明显适配另一条路线时。', 'then': '先看能复用哪些成装与两星打工牌，再决定换谁。换路线的代价也要计入，不能只比较两张最终阵容图。'},
            ]}
