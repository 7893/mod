#!/usr/bin/python3
from copy import deepcopy
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
XML = 'http://www.w3.org/XML/1998/namespace'
NS = {'w': W}
ET.register_namespace('w', W)

template = Path('/tmp/format_template.docx')
output = Path('/tmp/dashboard_requirement/全周期领导驾驶舱展示需求（初稿）.docx')

def tag(name):
    return f'{{{W}}}{name}'

def make_paragraph(prototype, text):
    p = deepcopy(prototype)
    run = p.find('.//w:r', NS)
    run_pr = deepcopy(run.find('w:rPr', NS)) if run is not None and run.find('w:rPr', NS) is not None else None
    for child in list(p):
        if child.tag != tag('pPr'):
            p.remove(child)
    new_run = ET.SubElement(p, tag('r'))
    if run_pr is not None:
        new_run.append(run_pr)
    text_node = ET.SubElement(new_run, tag('t'))
    text_node.set(f'{{{XML}}}space', 'preserve')
    text_node.text = text
    return p

with ZipFile(template, 'r') as zin:
    document = ET.fromstring(zin.read('word/document.xml'))
    body = document.find('w:body', NS)
    paragraphs = [node for node in list(body) if node.tag == tag('p')]
    if len(paragraphs) < 7:
        raise RuntimeError('Template does not contain expected paragraph styles')
    title_a, title_b, normal, heading_1, heading_2 = (
        paragraphs[1], paragraphs[2], paragraphs[4], paragraphs[5], paragraphs[6]
    )
    section = next((node for node in list(body) if node.tag == tag('sectPr')), None)
    for node in list(body):
        if node is not section:
            body.remove(node)

    content = [
        ('title_a', '全周期领导驾驶舱'),
        ('title_b', '建设需求汇报（初稿）'),
        ('heading_1', '一、建设背景及目标'),
        ('normal', '当前项目正处于建设、分批推广、数据准备和双轨运行并行推进阶段。建设事项、问题闭环、单位推广、凭证补录及运行情况分散在例会材料、问题台账和各类业务表单中，难以形成统一、及时的整体视图。'),
        ('normal', '拟建设全周期领导驾驶舱，面向领导和项目管理人员集中反映项目建设、推广及运行动态，及时识别滞后单位、突出风险和需协调事项，为例会调度和决策提供支撑。驾驶舱用于展示和研判，不替代现有业务系统及管理台账。'),
        ('heading_1', '二、总体展示内容'),
        ('heading_2', '（一）项目建设与问题闭环。'),
        ('normal', '展示建设事项总量、评审反馈、需解决事项、已解决已确认、已解决待确认、解决中、待专班讨论和转二期可研等数量、占比及较上期变化。按事项类别、所属模块、责任方和处理状态查看明细，重点呈现超期未解决和需协调事项。'),
        ('normal', '以当前例会口径为例，截至8月3日共提出506项，其中429项需解决、416项已完成闭环、29项转二期可研。后续驾驶舱应按统一口径自动反映上述数据变化。'),
        ('heading_2', '（二）分批推广与上线进度。'),
        ('normal', '按推广批次、管理单位和核算主体单位，展示应推广、已完成、推进中和未完成的单位数量及完成率，突出未按计划推进的单位。当前推广范围包括第一批399家、第二批138家、第三批132家单位。'),
        ('heading_2', '（三）数据准备与凭证补录。'),
        ('normal', '展示各批次凭证补录、凭证期初、静态数据和动态数据的应完成、已完成、未完成数量及完成率；按单位和期间查看未完成项目。对影响上线和双轨运行的数据准备不足情况进行提示。'),
        ('heading_2', '（四）双轨运行与凭证生成。'),
        ('normal', '展示满足双轨运行条件、已上线运行和未满足条件的单位情况；展示业务单据、单据生成凭证、集成凭证的累计、本周新增及较上周变化，并识别异常单位。第二批中已满足双轨运行条件的101家单位应作为当前重点跟踪对象。'),
        ('heading_2', '（五）风险预警与待协调事项。'),
        ('normal', '汇总影响建设交付、推广、数据收集、双轨运行和凭证生成的重点风险，明确责任单位、当前状态、影响范围和计划完成时间；将待专班讨论、长期未解决和跨部门协调事项形成清单，支持例会直接调度。'),
        ('heading_1', '三、展示与使用要求'),
        ('heading_2', '（一）总体视图与专题视图相结合。'),
        ('normal', '首页应集中呈现整体进度、关键完成率、重点风险和待协调事项；建设事项、推广进度、数据准备和运行情况应设置相应专题，便于查看具体单位、事项和问题明细。'),
        ('heading_2', '（二）统一口径并体现动态变化。'),
        ('normal', '各项指标应明确统计范围、统计截至时间、责任部门和更新频率，并与例会材料、问题登记表和推广台账保持一致。除累计数据外，应展示本周新增、较上周变化及完成率，反映推进趋势。'),
        ('heading_2', '（三）支持分层筛选与预警提示。'),
        ('normal', '应支持按推广批次、管理单位、核算主体单位、期间、事项类别和处理状态进行筛选，并可查看明细。对事项超期、数据未完成、双轨条件未满足、凭证生成或集成异常等情形采用红黄绿方式提示。'),
        ('heading_1', '四、数据提供与协同要求'),
        ('normal', '现有系统能够直接获取的数据，由相关系统按统一口径提供；问题台账、计划安排和需协调事项等暂不能自动获取的数据，由责任部门定期填报、确认。各业务部门负责数据的真实性、完整性和及时性，项目管理部门负责口径统筹及例会使用。'),
        ('heading_1', '五、需请领导确认的事项'),
        ('normal', '一是同意按“建设事项、推广进度、数据准备、双轨运行、风险协调”五类内容建设一期驾驶舱；二是同意以现有例会材料和项目台账为基础，统一核心指标口径及更新责任；三是请相关部门配合提供数据并及时确认异常、风险及待协调事项。'),
    ]
    prototypes = {'title_a': title_a, 'title_b': title_b, 'normal': normal, 'heading_1': heading_1, 'heading_2': heading_2}
    for kind, text in content:
        body.insert(len(body) - 1 if section is not None else len(body), make_paragraph(prototypes[kind], text))

    rendered = ET.tostring(document, encoding='utf-8', xml_declaration=True)
    with ZipFile(output, 'w', ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            payload = rendered if item.filename == 'word/document.xml' else zin.read(item.filename)
            zout.writestr(item, payload)

print(output)
