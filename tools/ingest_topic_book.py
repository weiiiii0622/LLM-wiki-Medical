#!/usr/bin/env python3
"""Topic-first ingest for chapter-split medical textbook markdown.

The script keeps raw files immutable and writes Codex-owned wiki pages. It is
intentionally deterministic so future sessions can rerun it after improving the
topic lexicon.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_BOOKS = ROOT / "raw" / "books" / "md"
WIKI = ROOT / "wiki"
TODAY = dt.date.today().isoformat()


TYPE_DIR = {
    "condition": "conditions",
    "drug": "drugs",
    "diagnostic": "diagnostics",
    "procedure": "procedures",
    "guideline": "guidelines",
    "physiology": "physiology",
    "anatomy": "anatomy",
    "concept": "concepts",
}


GENERIC_HEADINGS = {
    "定義",
    "病因",
    "分類",
    "病生理學",
    "病史詢問",
    "理學檢查",
    "治療",
    "診斷",
    "題目",
    "其他",
    "背景知識",
    "藥物介紹",
    "特殊",
    "檢查",
    "處置",
}


@dataclass(frozen=True)
class TopicSeed:
    kind: str
    slug: str
    title: str
    keywords: tuple[str, ...]
    summary: str


SEEDS: tuple[TopicSeed, ...] = (
    # Cardiovascular conditions and syndromes.
    TopicSeed("condition", "hypertension", "Hypertension (高血壓)", ("高血壓", "HTN", "hypertension"), "血壓長期升高造成心血管、腎臟與腦血管風險；本書涵蓋分類、次發性原因與急症處理。"),
    TopicSeed("condition", "hypertensive-emergency", "Hypertensive emergency (高血壓急症)", ("hypertensive emergency", "高血壓急症", "惡性高血壓", "急症"), "高血壓合併急性標的器官傷害時需快速評估與靜脈降壓。"),
    TopicSeed("condition", "secondary-hypertension", "Secondary hypertension (次發性高血壓)", ("次發性高血壓", "secondary hypertension", "腎動脈狹窄", "pheochromocytoma", "原發性醛固酮"), "需從腎臟、內分泌、血管與藥物原因找可逆病因。"),
    TopicSeed("condition", "aortic-dissection", "Aortic dissection (主動脈剝離)", ("主動脈剝離", "aortic dissection", "dissection"), "急性胸背痛與血壓控制相關的大血管急症。"),
    TopicSeed("condition", "aortic-aneurysm", "Aortic aneurysm (主動脈瘤)", ("主動脈瘤", "aortic aneurysm", "aneurysm"), "主動脈擴張與破裂風險相關，需依位置與大小評估追蹤或介入。"),
    TopicSeed("condition", "dyslipidemia", "Dyslipidemia (血脂異常)", ("高血脂", "血脂異常", "dyslipidemia", "hyperlipidemia", "LDL", "HDL", "triglyceride"), "血脂異常是動脈粥狀硬化與冠心症重要危險因子。"),
    TopicSeed("condition", "atherosclerosis", "Atherosclerosis (動脈粥狀硬化)", ("動脈粥狀硬化", "atherosclerosis", "atherosclerotic plaque", "plaque rupture"), "斑塊形成、破裂與血栓連結穩定型心絞痛和急性冠心症。"),
    TopicSeed("condition", "ischemic-heart-disease", "Ischemic heart disease (缺血性心臟病)", ("缺血性心臟病", "ischemic heart disease", "冠狀動脈疾病", "CAD"), "心肌供氧不足的疾病群，包含穩定型心絞痛與急性冠心症。"),
    TopicSeed("condition", "stable-angina", "Chronic stable angina (慢性穩定型心絞痛)", ("慢性穩定型心絞痛", "stable angina", "Chronic stable angina", "CCS"), "固定冠狀動脈斑塊造成可預測的運動誘發胸痛。"),
    TopicSeed("condition", "acute-coronary-syndrome", "Acute coronary syndrome (急性冠心症)", ("急性冠心症", "ACS", "Acute coronary syndrome", "UA", "NSTEMI", "STEMI"), "斑塊破裂與冠狀動脈血栓造成不穩定心絞痛或心肌梗塞。"),
    TopicSeed("condition", "unstable-angina", "Unstable angina (不穩定心絞痛)", ("不穩定心絞痛", "unstable angina", "UA", "crescendo angina"), "ACS 光譜中無心肌酵素上升的缺血狀態。"),
    TopicSeed("condition", "nstemi", "NSTEMI (非 ST 段上升心肌梗塞)", ("NSTEMI", "Non-ST", "Non ST", "Non Q wave MI"), "通常為心內膜下梗塞，心肌酵素上升但無 ST elevation。"),
    TopicSeed("condition", "stemi", "STEMI (ST 段上升心肌梗塞)", ("STEMI", "ST elevation myocardial infarction", "ST elevation", "STE", "Q wave MI"), "全層心肌缺血常出現 ST elevation，需再灌流策略。"),
    TopicSeed("condition", "wellens-syndrome", "Wellens syndrome (Wellens 氏症候群)", ("Wellens", "Wellens' syndrome", "前壁缺血", "LAD 嚴重狹窄"), "前胸導程 T 波變化提示 LAD 嚴重狹窄。"),
    TopicSeed("condition", "right-ventricular-infarction", "Right ventricular infarction (右心室梗塞)", ("右心梗塞", "右心室梗塞", "RV infarction", "V4R"), "常合併下壁梗塞；治療上需避免過度降低 preload。"),
    TopicSeed("condition", "heart-failure", "Heart failure (心臟衰竭)", ("心臟衰竭", "heart failure", "CHF", "HF", "NYHA", "Stage A", "Stage B", "Stage C", "Stage D"), "心臟結構或功能異常導致無法滿足身體需求，需分期、分型與治療。"),
    TopicSeed("condition", "hfref", "HFrEF (射出分率降低型心衰竭)", ("HFrEF", "systolic dysfunction", "收縮失能", "LVEF < 35", "LVEF <35"), "左心室收縮功能下降，藥物與裝置治療證據較完整。"),
    TopicSeed("condition", "hfpef", "HFpEF (射出分率保留型心衰竭)", ("HFpEF", "diastolic dysfunction", "舒張失能", "LVEF 是正常"), "舒張功能下降但 LVEF 可保留，治療重點偏症狀、血壓與共病控制。"),
    TopicSeed("condition", "cardiogenic-pulmonary-edema", "Cardiogenic pulmonary edema (心因性肺水腫)", ("肺水腫", "pulmonary edema", "急性心衰竭", "LMNO"), "心衰竭急性惡化常見表現，需氧氣、利尿與血管擴張等急性處置。"),
    TopicSeed("condition", "infective-endocarditis", "Infective endocarditis (感染性心內膜炎)", ("感染性心內膜炎", "infective endocarditis", "endocarditis", "Duke"), "菌血症造成心內膜或瓣膜感染，診斷依血液培養、心超與 Duke criteria。"),
    TopicSeed("condition", "rheumatic-heart-disease", "Rheumatic heart disease (風濕性心臟病)", ("風濕性", "rheumatic", "Jones", "rheumatic fever"), "鏈球菌感染後免疫反應可造成瓣膜病變。"),
    TopicSeed("condition", "aortic-stenosis", "Aortic stenosis (主動脈瓣狹窄)", ("主動脈瓣狹窄", "aortic stenosis", "AS"), "固定左心室出口阻塞，可有心絞痛、暈厥與心衰竭。"),
    TopicSeed("condition", "aortic-regurgitation", "Aortic regurgitation (主動脈瓣逆流)", ("主動脈瓣逆流", "aortic regurgitation", "AR"), "舒張期逆流造成容量負荷與脈壓變化。"),
    TopicSeed("condition", "mitral-stenosis", "Mitral stenosis (二尖瓣狹窄)", ("二尖瓣狹窄", "mitral stenosis", "MS"), "常與風濕性病變相關，造成左心房壓上升與肺鬱血。"),
    TopicSeed("condition", "mitral-regurgitation", "Mitral regurgitation (二尖瓣逆流)", ("二尖瓣逆流", "mitral regurgitation", "MR"), "收縮期逆流造成左心房與左心室容量負荷。"),
    TopicSeed("condition", "mitral-valve-prolapse", "Mitral valve prolapse (二尖瓣脫垂)", ("二尖瓣脫垂", "mitral valve prolapse", "MVP"), "瓣膜脫垂可造成收縮中期 click 與晚期收縮雜音。"),
    TopicSeed("condition", "cardiomyopathy", "Cardiomyopathy (心肌病變)", ("心肌症", "心肌病變", "cardiomyopathy"), "心肌結構或功能異常的疾病群。"),
    TopicSeed("condition", "dilated-cardiomyopathy", "Dilated cardiomyopathy (擴張型心肌病變)", ("擴張型心肌", "dilated cardiomyopathy", "DCM"), "心室擴張與收縮功能下降，可導致心衰竭。"),
    TopicSeed("condition", "hypertrophic-cardiomyopathy", "Hypertrophic cardiomyopathy (肥厚型心肌病變)", ("肥厚型心肌", "hypertrophic cardiomyopathy", "HCM"), "心肌肥厚與動態出口阻塞相關，使用 vasodilator 需小心。"),
    TopicSeed("condition", "restrictive-cardiomyopathy", "Restrictive cardiomyopathy (限制型心肌病變)", ("限制型心肌", "restrictive cardiomyopathy", "RCM"), "舒張受限造成充填障礙。"),
    TopicSeed("condition", "myocarditis", "Myocarditis (心肌炎)", ("心肌炎", "myocarditis"), "心肌發炎可造成胸痛、心律不整或心衰竭。"),
    TopicSeed("condition", "pericarditis", "Pericarditis (心包膜炎)", ("心包膜炎", "pericarditis"), "心包膜發炎可造成胸痛、摩擦音與心電圖變化。"),
    TopicSeed("condition", "pericardial-effusion", "Pericardial effusion (心包膜積液)", ("心包膜積液", "pericardial effusion"), "心包膜腔液體增加，需注意 tamponade 生理。"),
    TopicSeed("condition", "cardiac-tamponade", "Cardiac tamponade (心包膜填塞)", ("心包膜填塞", "cardiac tamponade", "tamponade", "Beck"), "心包壓升高限制心臟充填，可能造成休克。"),
    TopicSeed("condition", "constrictive-pericarditis", "Constrictive pericarditis (縮窄性心包膜炎)", ("縮窄性心包", "constrictive pericarditis"), "硬化心包限制舒張充填，可類似限制型心肌病變。"),
    TopicSeed("condition", "syncope", "Syncope (暈厥)", ("暈厥", "syncope"), "短暫意識喪失需分辨反射性、姿勢性、心因性與神經原因。"),
    TopicSeed("condition", "vasovagal-syncope", "Vasovagal syncope (血管迷走神經性暈厥)", ("血管迷走", "vasovagal"), "反射性暈厥常有誘發情境與前驅症狀。"),
    TopicSeed("condition", "orthostatic-hypotension", "Orthostatic hypotension (姿勢性低血壓)", ("姿勢性低血壓", "orthostatic hypotension"), "姿勢改變後血壓下降造成頭暈或暈厥。"),
    TopicSeed("condition", "atrial-fibrillation", "Atrial fibrillation (心房顫動)", ("心房顫動", "atrial fibrillation", "Af", "AF"), "常見心律不整，需評估 rate control、rhythm control 與抗凝。"),
    TopicSeed("condition", "atrial-flutter", "Atrial flutter (心房撲動)", ("心房撲動", "atrial flutter"), "心房大迴路造成鋸齒狀 flutter wave。"),
    TopicSeed("condition", "supraventricular-tachycardia", "Supraventricular tachycardia (上心室頻脈)", ("上心室頻脈", "SVT", "supraventricular tachycardia", "AVNRT"), "窄 QRS 規則性頻脈常與再迴路相關。"),
    TopicSeed("condition", "wolff-parkinson-white-syndrome", "Wolff-Parkinson-White syndrome (WPW 症候群)", ("WPW", "Wolff", "delta wave"), "副傳導路造成 pre-excitation，合併 AF 時治療需特別注意。"),
    TopicSeed("condition", "ventricular-tachycardia", "Ventricular tachycardia (心室頻脈)", ("心室頻脈", "ventricular tachycardia", "VT"), "寬 QRS 頻脈，可能導致血流動力學不穩。"),
    TopicSeed("condition", "ventricular-fibrillation", "Ventricular fibrillation (心室顫動)", ("心室顫動", "ventricular fibrillation", "VF"), "致命心律不整，需立即去顫與急救。"),
    TopicSeed("condition", "torsades-de-pointes", "Torsades de pointes (多型性心室頻脈)", ("torsades", "Torsades", "多型性心室頻脈", "long QT"), "QT 延長相關多型性 VT。"),
    TopicSeed("condition", "av-block", "Atrioventricular block (房室傳導阻滯)", ("房室傳導阻", "AV block", "atrioventricular block"), "房室傳導延遲或中斷，依程度決定追蹤或節律器。"),
    TopicSeed("condition", "bundle-branch-block", "Bundle branch block (束枝傳導阻滯)", ("束枝傳導", "bundle branch block", "LBBB", "RBBB"), "心室傳導延遲會影響 ECG 判讀與 CRT 評估。"),
    # Pulmonary conditions.
    TopicSeed("condition", "asthma", "Asthma (氣喘)", ("氣喘", "asthma", "bronchial asthma"), "可逆性氣流阻塞與慢性氣道發炎，治療依控制程度升降階。"),
    TopicSeed("condition", "copd", "COPD (慢性阻塞性肺疾病)", ("慢性阻塞性肺", "COPD", "chronic obstructive pulmonary"), "長期有害氣體暴露造成不可完全可逆的氣流阻塞。"),
    TopicSeed("condition", "chronic-bronchitis", "Chronic bronchitis (慢性支氣管炎)", ("慢性支氣管炎", "chronic bronchitis"), "COPD phenotype，以慢性咳嗽咳痰為核心。"),
    TopicSeed("condition", "emphysema", "Emphysema (肺氣腫)", ("肺氣腫", "emphysema"), "肺泡壁破壞與過度充氣造成氣體交換障礙。"),
    TopicSeed("condition", "bronchiectasis", "Bronchiectasis (支氣管擴張症)", ("支氣管擴張", "bronchiectasis"), "支氣管永久擴張，常有慢性痰與反覆感染。"),
    TopicSeed("condition", "interstitial-lung-disease", "Interstitial lung disease (間質性肺疾病)", ("間質性肺", "interstitial lung disease", "ILD"), "限制型通氣障礙與擴散能力下降相關的肺間質疾病群。"),
    TopicSeed("condition", "idiopathic-pulmonary-fibrosis", "Idiopathic pulmonary fibrosis (特發性肺纖維化)", ("特發性肺纖維化", "idiopathic pulmonary fibrosis", "IPF"), "原因不明的進行性纖維化 ILD。"),
    TopicSeed("condition", "sarcoidosis", "Sarcoidosis (類肉瘤病)", ("類肉瘤", "sarcoidosis"), "非乾酪性肉芽腫疾病，可侵犯肺與多器官。"),
    TopicSeed("condition", "pneumoconiosis", "Pneumoconiosis (塵肺症)", ("塵肺", "pneumoconiosis", "silicosis", "asbestosis"), "職業暴露造成的肺部纖維化疾病群。"),
    TopicSeed("condition", "pneumonia", "Pneumonia (肺炎)", ("肺炎", "pneumonia", "CAP", "HAP", "VAP"), "肺實質感染，需依場域與病原風險選擇抗生素。"),
    TopicSeed("condition", "community-acquired-pneumonia", "Community-acquired pneumonia (社區型肺炎)", ("社區型肺炎", "community-acquired pneumonia", "CAP"), "院外發生的肺炎，常以臨床嚴重度與病原風險決定治療。"),
    TopicSeed("condition", "hospital-acquired-pneumonia", "Hospital-acquired pneumonia (院內型肺炎)", ("院內型肺炎", "hospital-acquired pneumonia", "HAP"), "住院後發生的肺炎，需注意抗藥性菌。"),
    TopicSeed("condition", "ventilator-associated-pneumonia", "Ventilator-associated pneumonia (呼吸器相關肺炎)", ("呼吸器相關肺炎", "ventilator-associated pneumonia", "VAP"), "機械通氣後發生的肺炎，診斷與抗菌選擇較複雜。"),
    TopicSeed("condition", "lung-abscess", "Lung abscess (肺膿瘍)", ("肺膿瘍", "lung abscess"), "肺實質壞死形成膿腔，常與吸入性病原相關。"),
    TopicSeed("condition", "tuberculosis", "Tuberculosis (結核病)", ("結核", "tuberculosis", "TB", "AFB"), "分枝桿菌感染，可為肺結核或肺外結核。"),
    TopicSeed("condition", "latent-tuberculosis-infection", "Latent tuberculosis infection (潛伏結核感染)", ("潛伏結核", "latent tuberculosis", "LTBI"), "感染但無活動病灶，需依風險決定預防治療。"),
    TopicSeed("condition", "acute-respiratory-distress-syndrome", "ARDS (急性呼吸窘迫症候群)", ("急性呼吸窘迫", "ARDS", "acute respiratory distress"), "瀰漫性肺泡傷害造成低氧性呼吸衰竭，通氣策略需肺保護。"),
    TopicSeed("condition", "pulmonary-embolism", "Pulmonary embolism (肺栓塞)", ("肺栓塞", "pulmonary embolism", "PE", "肺血管栓塞"), "靜脈血栓進入肺循環造成呼吸困難、胸痛或休克。"),
    TopicSeed("condition", "pulmonary-hypertension", "Pulmonary hypertension (肺高壓)", ("肺高壓", "pulmonary hypertension", "PH"), "肺動脈壓升高，可源自心肺疾病或肺血管病變。"),
    TopicSeed("condition", "pleural-effusion", "Pleural effusion (肋膜積液)", ("肋膜積液", "pleural effusion", "pleural fluid"), "肋膜腔液體增加，需區分 transudate 與 exudate。"),
    TopicSeed("condition", "pneumothorax", "Pneumothorax (氣胸)", ("氣胸", "pneumothorax"), "空氣進入肋膜腔造成肺塌陷，張力性氣胸為急症。"),
    TopicSeed("condition", "empyema", "Empyema (膿胸)", ("膿胸", "empyema"), "肋膜腔感染積膿，常需引流與抗生素。"),
    TopicSeed("condition", "obstructive-sleep-apnea", "Obstructive sleep apnea (阻塞性睡眠呼吸中止症)", ("阻塞性睡眠", "sleep apnea", "OSA"), "睡眠中上呼吸道反覆阻塞造成缺氧與日間嗜睡。"),
    TopicSeed("condition", "lung-cancer", "Lung cancer (肺癌)", ("肺癌", "lung cancer", "NSCLC", "SCLC"), "肺部惡性腫瘤，需依組織型、分期與分子標記治療。"),
    TopicSeed("condition", "small-cell-lung-cancer", "Small-cell lung cancer (小細胞肺癌)", ("小細胞肺癌", "small-cell lung cancer", "SCLC"), "侵襲性高、常早期轉移的肺癌類型。"),
    TopicSeed("condition", "non-small-cell-lung-cancer", "Non-small-cell lung cancer (非小細胞肺癌)", ("非小細胞肺癌", "non-small-cell lung cancer", "NSCLC", "adenocarcinoma", "squamous cell"), "肺癌主要類型，治療依分期與 driver mutation。"),
    # Diagnostics, scores, and tests.
    TopicSeed("diagnostic", "blood-pressure-measurement", "Blood pressure measurement (血壓測量)", ("血壓測量", "blood pressure", "BP", "收縮壓", "舒張壓"), "正確量測與分類是高血壓診斷基礎。"),
    TopicSeed("diagnostic", "lipid-profile", "Lipid profile (血脂檢查)", ("lipid profile", "fasting lipid", "LDL", "HDL", "三酸甘油脂"), "血脂檢查用於 ASCVD 風險與治療目標追蹤。"),
    TopicSeed("diagnostic", "electrocardiography", "Electrocardiography, ECG (心電圖)", ("心電圖", "ECG", "EKG", "ST 段", "T 波", "Q wave"), "心電圖用於缺血、梗塞、傳導阻滯與心律不整判讀。"),
    TopicSeed("diagnostic", "stress-test", "Stress testing (壓力測試)", ("stress test", "Stress testing", "運動心電圖", "Treadmill", "Thallium"), "用於評估冠狀動脈缺血，依運動能力與基礎 ECG 選擇方式。"),
    TopicSeed("diagnostic", "cardiac-biomarkers", "Cardiac biomarkers (心肌酵素)", ("心肌酵素", "troponin", "CK-MB", "cardiac biomarkers", "enzyme"), "用於區分 UA 與 MI，並評估心肌壞死。"),
    TopicSeed("diagnostic", "echocardiography", "Echocardiography (心臟超音波)", ("心臟超音波", "echo", "echocardiography", "Cardiac echo", "LVEF"), "評估心室功能、瓣膜結構、心包膜積液與心衰竭分型。"),
    TopicSeed("diagnostic", "bnp", "BNP / NT-proBNP (腦利鈉胜肽)", ("BNP", "B-type natriuretic peptide", "NT-proBNP"), "心室壓力與容量負荷標記，可輔助心衰竭診斷與嚴重度評估。"),
    TopicSeed("diagnostic", "duke-criteria", "Duke criteria (Duke 診斷標準)", ("Duke", "Duke criteria"), "感染性心內膜炎的診斷架構。"),
    TopicSeed("diagnostic", "pulmonary-function-test", "Pulmonary function test, PFT (肺功能檢查)", ("肺功能", "pulmonary function", "PFT", "FEV", "FVC", "DLCO"), "區分阻塞型、限制型與擴散障礙。"),
    TopicSeed("diagnostic", "bronchodilator-reversibility-test", "Bronchodilator reversibility test (支氣管擴張劑可逆性試驗)", ("支氣管擴張劑可逆", "bronchodilator", "FEV", "200 mL", "12%"), "評估可逆性氣流阻塞，是氣喘診斷依據之一。"),
    TopicSeed("diagnostic", "methacholine-provocation-test", "Methacholine provocation test (Methacholine 支氣管激發試驗)", ("Methacholine", "provocation test", "PC20", "PD20"), "疑似氣喘但肺功能正常時可用來評估氣道高反應性。"),
    TopicSeed("diagnostic", "peak-expiratory-flow", "Peak expiratory flow, PEF (尖峰呼氣流速)", ("PEF", "PEFR", "尖峰呼氣", "peak expiratory flow"), "居家或連續追蹤氣喘變異性的簡易工具。"),
    TopicSeed("diagnostic", "arterial-blood-gas", "Arterial blood gas, ABG (動脈血氣)", ("ABG", "arterial blood gas", "血氣", "PaO2", "PaCO2", "A-a"), "評估氧合、通氣與酸鹼狀態。"),
    TopicSeed("diagnostic", "wells-score", "Wells score (Wells 分數)", ("Wells", "Wells score"), "用於肺栓塞臨床前測機率評估。"),
    TopicSeed("diagnostic", "d-dimer", "D-dimer (D-二聚體)", ("D-dimer", "D 二聚體", "D-二聚體"), "低風險肺栓塞排除策略常用檢驗。"),
    TopicSeed("diagnostic", "ct-pulmonary-angiography", "CT pulmonary angiography, CTPA (肺動脈電腦斷層血管攝影)", ("CTPA", "CT pulmonary angiography", "肺動脈電腦斷層", "血管攝影"), "肺栓塞常用影像診斷。"),
    TopicSeed("diagnostic", "light-criteria", "Light criteria (Light 標準)", ("Light", "Light criteria", "exudate", "transudate"), "區分肋膜積液為漏出液或滲出液。"),
    TopicSeed("diagnostic", "polysomnography", "Polysomnography (多項睡眠檢查)", ("polysomnography", "多項睡眠", "AHI", "sleep study"), "阻塞性睡眠呼吸中止症的診斷檢查。"),
    TopicSeed("diagnostic", "lung-cancer-staging", "Lung cancer staging (肺癌分期)", ("肺癌分期", "TNM", "staging", "stage"), "肺癌治療選擇依組織型與分期。"),
    # Drugs and treatment classes.
    TopicSeed("drug", "ace-inhibitors", "ACE inhibitors, ACEI (血管張力素轉化酶抑制劑)", ("ACEI", "ACE inhibitors", "angiotensin converting enzyme", "Enalapril", "Lisinopril", "Quinapril"), "降低 afterload 並抑制 RAA system，心衰竭與高血壓常用。"),
    TopicSeed("drug", "angiotensin-receptor-blockers", "Angiotensin receptor blockers, ARB (血管張力素受體阻斷劑)", ("ARB", "Angiotensin II receptor", "Valsartan", "Losartan", "Olmesartan"), "ACEI 類似效果但較少 bradykinin 相關咳嗽。"),
    TopicSeed("drug", "beta-blockers", "Beta blockers (乙型交感神經阻斷劑)", ("β blocker", "beta blocker", "Carvedilol", "Bisoprolol", "Metoprolol", "乙型交感"), "降低交感刺激與心臟做功；心衰竭需選有證據者並慢慢加量。"),
    TopicSeed("drug", "aldosterone-antagonists", "Aldosterone antagonists (醛固酮拮抗劑)", ("aldosterone antagonist", "Spironolactone", "Aldactone", "Eplerenone", "醛固酮"), "改善部分 HFrEF 病患預後，但需監測高血鉀與腎功能。"),
    TopicSeed("drug", "loop-diuretics", "Loop diuretics (亨利氏環利尿劑)", ("Loop diuretics", "Furosemide", "Lasix", "亨利氏", "利尿劑"), "改善鬱血與肺水腫症狀，長期死亡率效益需與疾病修飾藥物區分。"),
    TopicSeed("drug", "digoxin", "Digoxin (毛地黃)", ("Digoxin", "digitalis", "毛地黃", "Lanoxin"), "增加心縮力並可做 AF rate control；不能改善死亡率且有交互作用與中毒風險。"),
    TopicSeed("drug", "nitrates", "Nitrates (硝酸鹽類)", ("Nitrate", "nitroglycerin", "NTG", "硝化甘油", "硝酸"), "擴張靜脈與冠狀動脈，可緩解心絞痛與部分急性肺水腫。"),
    TopicSeed("drug", "hydralazine", "Hydralazine (肼屈嗪)", ("Hydralazine", "hydralazine"), "動脈擴張降低 afterload，可與 nitrate 合用於心衰竭。"),
    TopicSeed("drug", "aspirin", "Aspirin (阿斯匹靈)", ("Aspirin", "ASA", "阿斯匹靈"), "抗血小板藥物，用於冠心症血管保護；亦可誘發 aspirin-sensitive asthma。"),
    TopicSeed("drug", "p2y12-inhibitors", "P2Y12 inhibitors (P2Y12 抑制劑)", ("Clopidogrel", "P2Y12", "Dual antiplatlet", "雙重抗血小板"), "ACS 或 PCI 後常與 aspirin 合併。"),
    TopicSeed("drug", "heparin", "Heparin (肝素)", ("Heparin", "肝素", "aPTT", "LMWH", "Fondaparinux", "Bivalirudin"), "ACS 與血栓疾病抗凝治療常用，需注意 HIT。"),
    TopicSeed("drug", "statins", "Statins (史他汀類)", ("Statin", "statins", "LDL", "HMG-CoA"), "降低 LDL 與心血管風險，ACS/DM 等高風險族群目標較嚴格。"),
    TopicSeed("drug", "inhaled-corticosteroids", "Inhaled corticosteroids, ICS (吸入型類固醇)", ("ICS", "inhaled corticosteroid", "Budesonide", "Fluticasone", "Beclomethasone", "吸入型類固醇"), "氣喘控制核心藥物，依 step 調整劑量。"),
    TopicSeed("drug", "saba", "SABA (短效乙二型交感神經刺激劑)", ("SABA", "short acting beta2", "短效吸入型乙二型", "salbutamol", "albuterol"), "快速緩解支氣管收縮，但氣喘不宜只依賴 SABA。"),
    TopicSeed("drug", "laba", "LABA (長效乙二型交感神經刺激劑)", ("LABA", "long acting beta2", "Formoterol", "Salmeterol", "長效"), "氣喘需與 ICS 合用；formoterol 起效快可用於特定緩解策略。"),
    TopicSeed("drug", "lama", "LAMA (長效抗膽鹼劑)", ("LAMA", "long-acting muscarinic", "Tiotropium", "長效抗膽鹼"), "COPD 與部分嚴重氣喘 phenotype 可用。"),
    TopicSeed("drug", "leukotriene-receptor-antagonists", "Leukotriene receptor antagonists, LTRA (白三烯受體拮抗劑)", ("Leukotriene", "LTRA", "Montelukast", "Zafirlukast", "白三烯"), "氣喘替代或輔助藥物，對 aspirin-sensitive asthma 有用。"),
    TopicSeed("drug", "omalizumab", "Omalizumab (抗 IgE 單株抗體)", ("Omalizumab", "anti-IgE", "抗 IgE"), "嚴重 allergic eosinophilic asthma 可考慮。"),
    TopicSeed("drug", "anti-il5-antibodies", "Anti-IL-5 antibodies (抗 IL-5 單株抗體)", ("anti-IL5", "anti-IL-5", "抗 IL-5", "Eosinophil > 300"), "nonallergic eosinophilic asthma 控制不佳時可考慮。"),
    TopicSeed("drug", "theophylline", "Theophylline (茶鹼)", ("Theophylline", "Phyllocontin", "aminophylline", "茶鹼"), "氣喘輔助治療但治療窗窄，可造成心律不整或癲癇。"),
    TopicSeed("drug", "anti-tuberculosis-drugs", "Anti-tuberculosis drugs (抗結核藥物)", ("INH", "Rifampin", "Ethambutol", "Pyrazinamide", "抗結核"), "結核病治療核心藥物組合，需注意副作用與療程。"),
    TopicSeed("drug", "systemic-corticosteroids", "Systemic corticosteroids (全身性類固醇)", ("口服或靜脈類固醇", "systemic corticosteroid", "prednisolone", "methylprednisolone"), "氣喘/COPD 急性惡化與多種肺部發炎疾病常用。"),
    # Procedures and management workflows.
    TopicSeed("procedure", "percutaneous-coronary-intervention", "Percutaneous coronary intervention, PCI (經皮冠狀動脈介入)", ("PCI", "Percutaneous coronary intervention", "PTCA", "stent", "支架", "氣球擴張"), "冠狀動脈再灌流與血管再暢通方法。"),
    TopicSeed("procedure", "coronary-artery-bypass-graft", "Coronary artery bypass graft, CABG (冠狀動脈繞道術)", ("CABG", "Coronary Artery Bypass", "冠狀動脈繞道"), "外科冠狀動脈血管再暢通術。"),
    TopicSeed("procedure", "cardiac-catheterization", "Cardiac catheterization (心導管檢查)", ("心導管", "coronary arteriography", "catheterization", "血管攝影"), "評估冠狀動脈狹窄並可銜接介入治療。"),
    TopicSeed("procedure", "cardiac-resynchronization-therapy", "Cardiac resynchronization therapy, CRT (心臟再同步治療)", ("CRT", "Cardiac resynchronization", "Biventricular pacing", "再同步"), "符合 LVEF、NYHA 與傳導阻滯條件的心衰竭裝置治療。"),
    TopicSeed("procedure", "implantable-cardioverter-defibrillator", "Implantable cardioverter-defibrillator, ICD (植入式心臟去顫器)", ("ICD", "Implantable cardiac defibrillator", "去顫器"), "預防猝死的植入式裝置。"),
    TopicSeed("procedure", "pacemaker", "Pacemaker (心律調節器)", ("pacemaker", "節律器", "心律調節器"), "治療部分 bradyarrhythmia 或傳導阻滯。"),
    TopicSeed("procedure", "pericardiocentesis", "Pericardiocentesis (心包膜穿刺)", ("心包膜穿刺", "pericardiocentesis"), "心包膜填塞或大量積液的診斷/治療程序。"),
    TopicSeed("procedure", "mechanical-ventilation", "Mechanical ventilation (機械通氣)", ("呼吸器", "mechanical ventilation", "ventilator", "PEEP", "tidal volume"), "呼吸衰竭支持治療，設定與肺保護策略需依病況調整。"),
    TopicSeed("procedure", "noninvasive-ventilation", "Noninvasive ventilation, NIV (非侵襲性通氣)", ("NIV", "noninvasive", "BiPAP", "CPAP", "非侵襲性"), "以面罩提供正壓支持，常用於 COPD 急性惡化或 OSA。"),
    TopicSeed("procedure", "thoracentesis", "Thoracentesis (胸腔穿刺)", ("thoracentesis", "胸腔穿刺", "肋膜穿刺"), "肋膜積液診斷與治療程序。"),
    TopicSeed("procedure", "chest-tube-thoracostomy", "Chest tube thoracostomy (胸管置放)", ("胸管", "chest tube", "tube thoracostomy"), "氣胸、膿胸或大量肋膜積液的引流程序。"),
    TopicSeed("procedure", "cpap", "Continuous positive airway pressure, CPAP (連續正壓呼吸)", ("CPAP", "continuous positive airway pressure", "連續正壓"), "OSA 標準治療，也可作為非侵襲性正壓通氣模式。"),
    TopicSeed("procedure", "bronchoscopy", "Bronchoscopy (支氣管鏡)", ("bronchoscopy", "支氣管鏡"), "用於呼吸道檢查、採檢或部分治療。"),
    # Guidelines and frameworks.
    TopicSeed("guideline", "nyha-functional-class", "NYHA functional class (NYHA 心功能分級)", ("NYHA", "New York Heart Association", "functional class"), "以活動受限程度分級心衰竭症狀。"),
    TopicSeed("guideline", "acc-aha-heart-failure-stages", "ACC/AHA heart failure stages (ACC/AHA 心衰竭分期)", ("ACC/AHA", "Stage A", "Stage B", "Stage C", "Stage D"), "依危險因子、結構病變、症狀與末期狀態分期。"),
    TopicSeed("guideline", "ccs-angina-classification", "CCS angina classification (CCS 心絞痛分級)", ("CCS", "Canadian Cardiovascular Society"), "以活動受限程度分級穩定型心絞痛。"),
    TopicSeed("guideline", "gina-asthma-step-therapy", "GINA asthma step therapy (GINA 氣喘階梯治療)", ("GINA", "Step 1", "Step 2", "Step 3", "Step 4", "Step 5", "ICS/Formoterol"), "氣喘控制藥物依症狀與惡化風險升降階。"),
    TopicSeed("guideline", "gold-copd-assessment", "GOLD COPD assessment (GOLD 慢性阻塞性肺病評估)", ("GOLD", "Group B", "Group C", "Group D", "COPD"), "COPD 依症狀、肺功能與急性惡化風險分組治療。"),
    TopicSeed("guideline", "tb-treatment-framework", "Tuberculosis treatment framework (結核治療架構)", ("結核治療", "TB treatment", "DOTS", "RIPE"), "結核病需多藥合併與完整療程。"),
    TopicSeed("guideline", "ards-berlin-definition", "Berlin definition of ARDS (ARDS Berlin 定義)", ("Berlin", "ARDS", "PaO2/FiO2"), "ARDS 以時間、影像、氧合與非心因性水腫定義。"),
    # Physiology, anatomy, and concepts.
    TopicSeed("physiology", "raa-system", "Renin-angiotensin-aldosterone system, RAAS (腎素-血管張力素-醛固酮系統)", ("RAA", "RAAS", "renin", "angiotensin", "aldosterone"), "心衰竭與高血壓治療的重要神經荷爾蒙路徑。"),
    TopicSeed("physiology", "preload-afterload", "Preload and afterload (前負荷與後負荷)", ("preload", "afterload", "前負荷", "後負荷"), "理解心衰竭、瓣膜病與血管擴張藥物效果的基本概念。"),
    TopicSeed("physiology", "ventricular-remodeling", "Ventricular remodeling (心室重塑)", ("remodeling", "心室重塑", "纖維化", "apoptosis"), "心肌傷害後結構與功能變化，與心衰竭進展相關。"),
    TopicSeed("physiology", "coronary-circulation", "Coronary circulation (冠狀動脈循環)", ("冠狀動脈", "LAD", "LCX", "RCA", "posterior descending"), "冠狀動脈解剖決定心肌缺血位置與 ECG 導程變化。"),
    TopicSeed("physiology", "airway-inflammation", "Airway inflammation (氣道發炎)", ("氣道發炎", "Th2", "eosinophil", "neutrophil", "TSLP", "IL-5", "IL33"), "氣喘 phenotype 與控制藥物選擇的免疫基礎。"),
    TopicSeed("physiology", "ventilation-perfusion", "Ventilation-perfusion matching, V/Q (通氣灌流匹配)", ("V/Q", "ventilation perfusion", "通氣灌流", "dead space", "shunt"), "低氧血症與肺栓塞、肺炎、ARDS 等疾病的重要生理概念。"),
    TopicSeed("physiology", "oxygenation-and-ventilation", "Oxygenation and ventilation (氧合與通氣)", ("氧合", "通氣", "oxygenation", "ventilation", "PaO2", "PaCO2"), "區分低氧與二氧化碳滯留，連結血氣與呼吸器設定。"),
    TopicSeed("anatomy", "coronary-arteries", "Coronary arteries (冠狀動脈)", ("LAD", "LCX", "RCA", "left main", "冠狀動脈"), "LAD、LCX、RCA 與心肌區域及 ECG 導程定位相關。"),
    TopicSeed("anatomy", "heart-valves", "Heart valves (心臟瓣膜)", ("主動脈瓣", "二尖瓣", "三尖瓣", "肺動脈瓣", "valve"), "瓣膜狹窄或逆流造成壓力/容量負荷與雜音。"),
    TopicSeed("anatomy", "pleura", "Pleura (肋膜)", ("肋膜", "pleura", "pleural"), "肋膜腔疾病包含積液、氣胸與膿胸。"),
    TopicSeed("anatomy", "airways", "Airways (氣道)", ("氣道", "airway", "bronchus", "支氣管"), "氣喘、COPD、支氣管擴張與呼吸器管理的核心結構。"),
    TopicSeed("concept", "antiplatelet-therapy", "Antiplatelet therapy (抗血小板治療)", ("抗血小板", "antiplatlet", "antiplatelet", "Aspirin", "Clopidogrel", "GP IIb"), "冠心症與 PCI 的核心血栓預防策略。"),
    TopicSeed("concept", "anticoagulation", "Anticoagulation (抗凝治療)", ("抗凝", "anticoagulation", "Heparin", "warfarin", "NOAC", "aPTT"), "血栓疾病與 AF 中風預防的重要治療概念。"),
    TopicSeed("concept", "revascularization", "Revascularization (血管再暢通)", ("revascularization", "再暢通", "PCI", "CABG"), "以 PCI 或 CABG 改善冠狀動脈血流。"),
    TopicSeed("concept", "rate-control", "Rate control (心率控制)", ("rate control", "心率控制", "Digoxin", "beta blocker"), "AF 等心律不整控制心室反應速率的策略。"),
    TopicSeed("concept", "rhythm-control", "Rhythm control (節律控制)", ("rhythm control", "節律控制", "cardioversion", "antiarrhythmic"), "恢復或維持竇性心律的策略。"),
    TopicSeed("concept", "oxygen-therapy", "Oxygen therapy (氧氣治療)", ("氧氣", "oxygen therapy", "O2", "鼻導管", "面罩"), "低氧血症與急性呼吸困難的支持治療。"),
    TopicSeed("concept", "smoking-cessation", "Smoking cessation (戒菸)", ("戒菸", "smoking cessation", "抽菸"), "心血管與肺部疾病最重要的風險修正之一。"),
    TopicSeed("concept", "lung-protective-ventilation", "Lung-protective ventilation (肺保護性通氣)", ("肺保護", "low tidal volume", "tidal volume", "ARDSNet"), "ARDS 通氣策略重點是低潮氣容積與避免通氣傷害。"),
)

SECOND_BOOK_SEEDS: tuple[TopicSeed, ...] = (
    # Gastroenterology conditions.
    TopicSeed("condition", "dysphagia", "Dysphagia (吞嚥困難)", ("吞嚥困難", "dysphagia"), "吞嚥困難需區分 oropharyngeal 與 esophageal causes，並注意進行性症狀與警訊。"),
    TopicSeed("condition", "achalasia", "Achalasia (食道弛緩不能)", ("食道弛緩不能", "achalasia", "bird beak"), "下食道括約肌放鬆不全與食道蠕動異常造成吞嚥困難。"),
    TopicSeed("condition", "gastroesophageal-reflux-disease", "Gastroesophageal reflux disease, GERD (胃食道逆流)", ("胃食道逆流", "GERD", "reflux esophagitis", "逆流性食道炎"), "胃酸逆流造成 heartburn、食道炎或併發症，治療包含生活型態與抑酸藥物。"),
    TopicSeed("condition", "barrett-esophagus", "Barrett esophagus (巴洛氏食道)", ("Barrett", "巴洛氏食道", "intestinal metaplasia"), "慢性 GERD 相關腸化生，是食道腺癌風險因子。"),
    TopicSeed("condition", "esophageal-cancer", "Esophageal cancer (食道癌)", ("食道癌", "esophageal cancer", "esophageal adenocarcinoma", "squamous cell carcinoma"), "食道癌依組織型與位置連結 GERD、Barrett esophagus、抽菸與酒精等風險。"),
    TopicSeed("condition", "peptic-ulcer-disease", "Peptic ulcer disease (消化性潰瘍)", ("消化性潰瘍", "peptic ulcer", "胃潰瘍", "十二指腸潰瘍", "duodenal ulcer"), "胃或十二指腸黏膜潰瘍，常與 H. pylori、NSAID 或酸分泌相關。"),
    TopicSeed("condition", "helicobacter-pylori-infection", "Helicobacter pylori infection (幽門螺旋桿菌感染)", ("Helicobacter pylori", "H. pylori", "幽門螺旋桿菌"), "H. pylori 與消化性潰瘍、胃炎、胃癌及 MALT lymphoma 風險相關。"),
    TopicSeed("condition", "gastritis", "Gastritis (胃炎)", ("胃炎", "gastritis"), "胃黏膜發炎可由感染、藥物、自體免疫或化學刺激造成。"),
    TopicSeed("condition", "gastric-cancer", "Gastric cancer (胃癌)", ("胃癌", "gastric cancer", "gastric adenocarcinoma"), "胃部惡性腫瘤，與 H. pylori、萎縮性胃炎與腸化生等風險相關。"),
    TopicSeed("condition", "gastrointestinal-stromal-tumor", "Gastrointestinal stromal tumor, GIST (胃腸基質瘤)", ("GIST", "gastrointestinal stromal tumor", "胃腸基質瘤"), "胃腸道間質腫瘤常與 KIT/PDGFRA 訊號相關。"),
    TopicSeed("condition", "upper-gastrointestinal-bleeding", "Upper gastrointestinal bleeding (上消化道出血)", ("上消化道出血", "UGIB", "hematemesis", "melena", "吐血", "黑便"), "上消化道出血常見來源包含潰瘍、靜脈曲張、Mallory-Weiss tear 等。"),
    TopicSeed("condition", "lower-gastrointestinal-bleeding", "Lower gastrointestinal bleeding (下消化道出血)", ("下消化道出血", "LGIB", "hematochezia", "血便"), "下消化道出血需依血流動力學與出血型態評估來源。"),
    TopicSeed("condition", "mallory-weiss-tear", "Mallory-Weiss tear (Mallory-Weiss 裂傷)", ("Mallory-Weiss", "Mallory Weiss", "撕裂"), "劇烈嘔吐後食道胃交界黏膜裂傷可造成上消化道出血。"),
    TopicSeed("condition", "diarrhea", "Diarrhea (腹瀉)", ("腹瀉", "diarrhea"), "腹瀉需依急慢性、發炎性/非發炎性、滲透性/分泌性與感染風險分類。"),
    TopicSeed("condition", "infectious-diarrhea", "Infectious diarrhea (感染性腹瀉)", ("感染性腹瀉", "infectious diarrhea", "Salmonella", "Shigella", "Campylobacter", "C. difficile"), "感染性腹瀉依病原、血便、發燒與旅遊/抗生素暴露判斷。"),
    TopicSeed("condition", "inflammatory-bowel-disease", "Inflammatory bowel disease, IBD (發炎性腸道疾病)", ("發炎性腸道疾病", "IBD", "inflammatory bowel disease"), "IBD 包含 Crohn disease 與 ulcerative colitis，需整合臨床、內視鏡與病理。"),
    TopicSeed("condition", "crohn-disease", "Crohn disease (克隆氏症)", ("Crohn", "克隆氏", "Crohn's disease"), "可侵犯全消化道的 transmural IBD，常有 skip lesions、瘻管或狹窄。"),
    TopicSeed("condition", "ulcerative-colitis", "Ulcerative colitis (潰瘍性結腸炎)", ("潰瘍性結腸炎", "ulcerative colitis", "UC"), "由直腸連續向近端侵犯的黏膜層 IBD。"),
    TopicSeed("condition", "irritable-bowel-syndrome", "Irritable bowel syndrome, IBS (腸躁症)", ("腸躁症", "IBS", "irritable bowel syndrome"), "功能性腸道症候群，以腹痛與排便習慣改變為核心。"),
    TopicSeed("condition", "celiac-disease", "Celiac disease (乳糜瀉)", ("celiac", "乳糜瀉", "gluten"), "gluten 相關免疫性小腸病變，可造成吸收不良與腹瀉。"),
    TopicSeed("condition", "jaundice", "Jaundice (黃疸)", ("黃疸", "jaundice", "bilirubin"), "黃疸依 bilirubin 類型與肝前、肝內、肝後原因分類。"),
    TopicSeed("condition", "abnormal-liver-function-tests", "Abnormal liver function tests (肝功能異常)", ("肝功能異常", "LFT", "AST", "ALT", "ALP", "GGT"), "肝功能檢查異常需判斷 hepatocellular、cholestatic 或 mixed pattern。"),
    TopicSeed("condition", "acute-pancreatitis", "Acute pancreatitis (急性胰臟炎)", ("急性胰臟炎", "acute pancreatitis", "Ranson"), "急性胰臟發炎常見原因為膽石與酒精，需評估嚴重度與併發症。"),
    TopicSeed("condition", "chronic-pancreatitis", "Chronic pancreatitis (慢性胰臟炎)", ("慢性胰臟炎", "chronic pancreatitis"), "反覆胰臟發炎造成纖維化、疼痛、外分泌或內分泌不足。"),
    TopicSeed("condition", "pancreatic-cancer", "Pancreatic cancer (胰臟癌)", ("胰臟癌", "pancreatic cancer", "pancreatic adenocarcinoma"), "胰臟惡性腫瘤常以阻塞性黃疸、體重下降或腹背痛表現。"),
    TopicSeed("condition", "cholelithiasis", "Cholelithiasis (膽結石)", ("膽結石", "gallstone", "cholelithiasis"), "膽囊或膽道結石可造成 biliary colic、膽囊炎、膽管炎或胰臟炎。"),
    TopicSeed("condition", "acute-cholecystitis", "Acute cholecystitis (急性膽囊炎)", ("急性膽囊炎", "acute cholecystitis", "Murphy"), "膽囊管阻塞後發炎，典型有右上腹痛與 Murphy sign。"),
    TopicSeed("condition", "acute-cholangitis", "Acute cholangitis (急性膽管炎)", ("急性膽管炎", "acute cholangitis", "Charcot", "Reynolds"), "膽道阻塞合併感染，可出現 Charcot triad 或 Reynolds pentad。"),
    TopicSeed("condition", "choledocholithiasis", "Choledocholithiasis (總膽管結石)", ("總膽管結石", "choledocholithiasis", "CBD stone"), "總膽管結石可造成阻塞性黃疸、膽管炎或胰臟炎。"),
    # Hepatology conditions.
    TopicSeed("condition", "viral-hepatitis", "Viral hepatitis (病毒性肝炎)", ("病毒性肝炎", "viral hepatitis"), "病毒性肝炎包含 HAV、HBV、HCV、HDV、HEV，臨床可急性或慢性。"),
    TopicSeed("condition", "hepatitis-a", "Hepatitis A (A 型肝炎)", ("A型肝炎", "A 型肝炎", "HAV", "hepatitis A"), "HAV 多經糞口傳染，通常急性、自限性。"),
    TopicSeed("condition", "hepatitis-b", "Hepatitis B (B 型肝炎)", ("B型肝炎", "B 型肝炎", "HBV", "hepatitis B", "HBsAg", "anti-HBs", "HBeAg"), "HBV 可造成急性、慢性肝炎、肝硬化與肝細胞癌風險。"),
    TopicSeed("condition", "hepatitis-c", "Hepatitis C (C 型肝炎)", ("C型肝炎", "C 型肝炎", "HCV", "hepatitis C"), "HCV 易慢性化並與肝硬化、肝細胞癌相關。"),
    TopicSeed("condition", "hepatitis-d", "Hepatitis D (D 型肝炎)", ("D型肝炎", "D 型肝炎", "HDV", "hepatitis D"), "HDV 需依賴 HBV，可造成 coinfection 或 superinfection。"),
    TopicSeed("condition", "hepatitis-e", "Hepatitis E (E 型肝炎)", ("E型肝炎", "E 型肝炎", "HEV", "hepatitis E"), "HEV 多經糞口傳染，孕婦感染風險需特別注意。"),
    TopicSeed("condition", "alcohol-associated-liver-disease", "Alcohol-associated liver disease (酒精性肝病)", ("酒精性肝病", "alcoholic liver disease", "alcoholic hepatitis"), "酒精造成脂肪肝、酒精性肝炎、纖維化或肝硬化。"),
    TopicSeed("condition", "nonalcoholic-fatty-liver-disease", "Nonalcoholic fatty liver disease, NAFLD (非酒精性脂肪肝)", ("脂肪肝", "NAFLD", "NASH", "nonalcoholic fatty"), "代謝症候群相關脂肪肝可進展至 steatohepatitis、纖維化或肝硬化。"),
    TopicSeed("condition", "autoimmune-hepatitis", "Autoimmune hepatitis (自體免疫性肝炎)", ("自體免疫性肝炎", "autoimmune hepatitis", "ANA", "ASMA"), "自體免疫造成 hepatocellular liver injury，需與病毒、藥物等鑑別。"),
    TopicSeed("condition", "drug-induced-liver-injury", "Drug-induced liver injury, DILI (藥物性肝損傷)", ("藥物性肝", "DILI", "drug-induced liver"), "藥物或毒物造成肝細胞型、膽汁鬱積型或混合型肝損傷。"),
    TopicSeed("condition", "liver-cirrhosis", "Liver cirrhosis (肝硬化)", ("肝硬化", "cirrhosis", "liver cirrhosis"), "慢性肝病末期結構重塑，伴隨門脈高壓與肝衰竭併發症。"),
    TopicSeed("condition", "portal-hypertension", "Portal hypertension (門脈高壓)", ("門脈高壓", "portal hypertension", "portal pressure"), "門脈壓上升可造成靜脈曲張、脾腫大、腹水與側枝循環。"),
    TopicSeed("condition", "ascites", "Ascites (腹水)", ("腹水", "ascites", "SAAG"), "腹腔積液常見於肝硬化門脈高壓，需以 SAAG 與感染風險評估。"),
    TopicSeed("condition", "spontaneous-bacterial-peritonitis", "Spontaneous bacterial peritonitis, SBP (自發性細菌性腹膜炎)", ("自發性細菌性腹膜炎", "SBP", "spontaneous bacterial peritonitis"), "肝硬化腹水感染，診斷常依腹水 PMN 計數與培養。"),
    TopicSeed("condition", "hepatic-encephalopathy", "Hepatic encephalopathy (肝腦病變)", ("肝腦病變", "hepatic encephalopathy", "肝昏迷", "asterixis"), "肝衰竭與門體分流相關神經精神症候群，常由出血、感染、便秘等誘發。"),
    TopicSeed("condition", "esophageal-varices", "Esophageal varices (食道靜脈曲張)", ("食道靜脈曲張", "esophageal varices", "variceal bleeding"), "門脈高壓造成食道靜脈曲張，可發生大量上消化道出血。"),
    TopicSeed("condition", "gastric-varices", "Gastric varices (胃靜脈曲張)", ("胃靜脈曲張", "gastric varices"), "胃靜脈曲張出血風險與位置、門脈高壓及處置選擇相關。"),
    TopicSeed("condition", "hepatorenal-syndrome", "Hepatorenal syndrome (肝腎症候群)", ("肝腎症候群", "hepatorenal syndrome", "HRS", "terlipressin"), "肝硬化與門脈高壓造成的功能性腎衰竭，需排除其他腎損傷。"),
    TopicSeed("condition", "hepatopulmonary-syndrome", "Hepatopulmonary syndrome (肝肺症候群)", ("肝肺症候群", "hepatopulmonary syndrome", "platypnea", "orthodeoxia"), "肝病造成肺內血管擴張與 shunt，典型可有 platypnea-orthodeoxia。"),
    TopicSeed("condition", "liver-abscess", "Liver abscess (肝膿瘍)", ("肝膿瘍", "liver abscess", "amebic abscess", "pyogenic abscess"), "肝臟膿瘍可為細菌性或阿米巴性，表現發燒與右上腹痛。"),
    TopicSeed("condition", "hepatocellular-carcinoma", "Hepatocellular carcinoma, HCC (肝細胞癌)", ("肝細胞癌", "HCC", "hepatocellular carcinoma", "肝癌"), "HCC 常源自慢性 HBV/HCV、肝硬化或脂肪肝背景。"),
    # Endocrine/metabolic conditions.
    TopicSeed("condition", "pituitary-adenoma", "Pituitary adenoma (腦垂體腺瘤)", ("腦垂體腺瘤", "pituitary adenoma", "macroadenoma", "microadenoma"), "腦垂體腺瘤可造成荷爾蒙過量、低下或壓迫症狀。"),
    TopicSeed("condition", "hyperprolactinemia", "Hyperprolactinemia (高泌乳素血症)", ("高泌乳素", "hyperprolactinemia", "prolactinoma", "泌乳素瘤"), "泌乳素升高可造成月經異常、溢乳、性腺功能低下。"),
    TopicSeed("condition", "acromegaly", "Acromegaly (肢端肥大症)", ("肢端肥大", "acromegaly", "IGF-1", "GH"), "成人 GH 過多造成肢端肥大、代謝與心血管併發症。"),
    TopicSeed("condition", "diabetes-insipidus", "Diabetes insipidus (尿崩症)", ("尿崩症", "diabetes insipidus", "DI", "ADH"), "ADH 缺乏或腎臟反應不良造成多尿與高鈉風險。"),
    TopicSeed("condition", "siadh", "SIADH (抗利尿激素分泌不當症候群)", ("SIADH", "抗利尿激素分泌不當"), "ADH 過多造成低鈉血症與濃縮尿。"),
    TopicSeed("condition", "hypopituitarism", "Hypopituitarism (腦垂體功能低下)", ("腦垂體功能低下", "hypopituitarism", "Sheehan"), "腦垂體荷爾蒙缺乏造成多軸內分泌不足。"),
    TopicSeed("condition", "hyperthyroidism", "Hyperthyroidism (甲狀腺亢進)", ("甲狀腺亢進", "hyperthyroidism", "thyrotoxicosis"), "甲狀腺素過多造成高代謝症狀、心悸、體重下降與眼/皮膚表現。"),
    TopicSeed("condition", "graves-disease", "Graves disease (葛瑞夫茲病)", ("Graves", "葛瑞夫", "TSI", "TRAb"), "自體免疫刺激 TSH receptor，是甲狀腺亢進常見原因。"),
    TopicSeed("condition", "hypothyroidism", "Hypothyroidism (甲狀腺低下)", ("甲狀腺低下", "hypothyroidism", "myxedema"), "甲狀腺素不足造成低代謝症狀與 TSH/T4 變化。"),
    TopicSeed("condition", "hashimoto-thyroiditis", "Hashimoto thyroiditis (橋本氏甲狀腺炎)", ("Hashimoto", "橋本", "慢性淋巴球性甲狀腺炎"), "自體免疫甲狀腺炎，常導致甲狀腺低下。"),
    TopicSeed("condition", "thyroid-storm", "Thyroid storm (甲狀腺風暴)", ("甲狀腺風暴", "thyroid storm"), "嚴重 thyrotoxicosis 急症，需快速支持與抑制甲狀腺素作用/合成/釋放。"),
    TopicSeed("condition", "thyroid-nodule", "Thyroid nodule (甲狀腺結節)", ("甲狀腺結節", "thyroid nodule"), "甲狀腺結節需以超音波、TSH 與細針抽吸風險分層。"),
    TopicSeed("condition", "thyroid-cancer", "Thyroid cancer (甲狀腺癌)", ("甲狀腺癌", "thyroid cancer", "papillary thyroid", "follicular thyroid", "medullary thyroid", "anaplastic"), "甲狀腺惡性腫瘤依病理型態預後與治療不同。"),
    TopicSeed("condition", "adrenal-insufficiency", "Adrenal insufficiency (腎上腺功能不全)", ("腎上腺功能不全", "adrenal insufficiency", "Addison", "adrenal crisis"), "皮質醇不足可造成疲倦、低血壓、低鈉與危急 adrenal crisis。"),
    TopicSeed("condition", "cushing-syndrome", "Cushing syndrome (庫欣氏症候群)", ("Cushing", "庫欣", "hypercortisolism"), "皮質醇過多造成中心肥胖、紫紋、高血壓、糖尿病與骨質疏鬆。"),
    TopicSeed("condition", "primary-aldosteronism", "Primary aldosteronism (原發性醛固酮症)", ("原發性醛固酮", "primary aldosteronism", "Conn"), "醛固酮自主分泌造成高血壓與低血鉀。"),
    TopicSeed("condition", "pheochromocytoma", "Pheochromocytoma (嗜鉻細胞瘤)", ("嗜鉻細胞瘤", "pheochromocytoma", "catecholamine"), "兒茶酚胺分泌腫瘤可造成陣發性高血壓、頭痛、心悸、盜汗。"),
    TopicSeed("condition", "diabetes-mellitus", "Diabetes mellitus (糖尿病)", ("糖尿病", "diabetes mellitus", "DM", "HbA1c", "OGTT"), "慢性高血糖疾病群，診斷、分型、治療與併發症監測都需系統化。"),
    TopicSeed("condition", "type-1-diabetes", "Type 1 diabetes mellitus (第 1 型糖尿病)", ("第1型糖尿病", "第 1 型糖尿病", "T1DM", "type 1 diabetes"), "自體免疫 β cell 破壞造成絕對胰島素缺乏，常需胰島素治療。"),
    TopicSeed("condition", "type-2-diabetes", "Type 2 diabetes mellitus (第 2 型糖尿病)", ("第2型糖尿病", "第 2 型糖尿病", "T2DM", "type 2 diabetes", "insulin resistance"), "胰島素阻抗與 β cell 功能下降造成慢性高血糖。"),
    TopicSeed("condition", "prediabetes", "Prediabetes (糖尿病前期)", ("糖尿病前期", "prediabetes", "IFG", "IGT"), "血糖高於正常但未達糖尿病，生活型態介入可降低進展。"),
    TopicSeed("condition", "metabolic-syndrome", "Metabolic syndrome (新陳代謝症候群)", ("新陳代謝症候群", "metabolic syndrome", "insulin resistance syndrome"), "腹部肥胖、高血壓、高血糖與血脂異常聚集，增加糖尿病與心血管風險。"),
    TopicSeed("condition", "diabetic-ketoacidosis", "Diabetic ketoacidosis, DKA (糖尿病酮酸中毒)", ("糖尿病酮酸中毒", "DKA", "diabetic ketoacidosis"), "胰島素不足造成高血糖、酮酸中毒與脫水的急性併發症。"),
    TopicSeed("condition", "hyperosmolar-hyperglycemic-state", "Hyperosmolar hyperglycemic state, HHS (高滲透壓高血糖狀態)", ("高滲透壓", "HHS", "hyperosmolar hyperglycemic"), "嚴重高血糖與高滲透壓，酮酸較不明顯，常見於第 2 型糖尿病。"),
    TopicSeed("condition", "diabetic-nephropathy", "Diabetic nephropathy (糖尿病腎病變)", ("糖尿病腎病變", "diabetic nephropathy", "albuminuria"), "糖尿病微血管併發症，可有白蛋白尿與腎功能下降。"),
    TopicSeed("condition", "diabetic-retinopathy", "Diabetic retinopathy (糖尿病視網膜病變)", ("糖尿病視網膜", "diabetic retinopathy"), "糖尿病微血管眼部併發症，需定期眼底檢查。"),
    TopicSeed("condition", "diabetic-neuropathy", "Diabetic neuropathy (糖尿病神經病變)", ("糖尿病神經病變", "diabetic neuropathy"), "糖尿病周邊或自主神經併發症，影響足部照護與生活品質。"),
    TopicSeed("condition", "hypoglycemia", "Hypoglycemia (低血糖)", ("低血糖", "hypoglycemia"), "血糖過低可由胰島素、促泌劑、禁食或內分泌疾病造成。"),
    TopicSeed("condition", "gestational-diabetes", "Gestational diabetes mellitus (妊娠糖尿病)", ("妊娠糖尿病", "gestational diabetes", "GDM"), "懷孕期間診斷的糖代謝異常，影響母胎風險與後續糖尿病風險。"),
    TopicSeed("condition", "hyperuricemia", "Hyperuricemia (高尿酸血症)", ("高尿酸", "hyperuricemia", "uric acid"), "尿酸升高與痛風、腎結石及代謝風險相關。"),
    TopicSeed("condition", "gout", "Gout (痛風)", ("痛風", "gout"), "尿酸鹽結晶造成急性關節炎與慢性痛風石。"),
    TopicSeed("condition", "hyperparathyroidism", "Hyperparathyroidism (副甲狀腺亢進)", ("副甲狀腺亢進", "hyperparathyroidism", "PTH"), "PTH 過多造成高血鈣、骨病變、腎結石或神經腸胃症狀。"),
    TopicSeed("condition", "hypoparathyroidism", "Hypoparathyroidism (副甲狀腺低下)", ("副甲狀腺低下", "hypoparathyroidism"), "PTH 不足造成低血鈣與高磷。"),
    TopicSeed("condition", "hypercalcemia", "Hypercalcemia (高血鈣)", ("高血鈣", "hypercalcemia"), "高血鈣常見原因包含副甲狀腺亢進與惡性腫瘤。"),
    TopicSeed("condition", "hypocalcemia", "Hypocalcemia (低血鈣)", ("低血鈣", "hypocalcemia", "tetany"), "低血鈣可造成神經肌肉興奮、手足搐搦或心電圖變化。"),
    TopicSeed("condition", "osteoporosis", "Osteoporosis (骨質疏鬆症)", ("骨質疏鬆", "osteoporosis", "DEXA"), "骨量下降與骨折風險增加，與鈣磷、性腺、甲狀腺、副甲狀腺等軸相關。"),
    TopicSeed("condition", "hypogonadism", "Hypogonadism (性腺功能低下)", ("性腺功能低下", "hypogonadism"), "性腺荷爾蒙不足可源自原發性性腺或中樞病變。"),
    TopicSeed("condition", "polycystic-ovary-syndrome", "Polycystic ovary syndrome, PCOS (多囊性卵巢症候群)", ("多囊性卵巢", "PCOS", "polycystic ovary"), "排卵異常、高雄性素與代謝風險相關症候群。"),
    # Diagnostics.
    TopicSeed("diagnostic", "upper-endoscopy", "Upper endoscopy, EGD (上消化道內視鏡)", ("上消化道內視鏡", "EGD", "胃鏡", "esophagoscopy", "endoscopy"), "評估食道、胃、十二指腸病灶與上消化道出血的重要檢查。"),
    TopicSeed("diagnostic", "colonoscopy", "Colonoscopy (大腸鏡)", ("大腸鏡", "colonoscopy"), "評估下消化道出血、IBD、腫瘤與慢性腹瀉的重要檢查。"),
    TopicSeed("diagnostic", "helicobacter-pylori-testing", "Helicobacter pylori testing (幽門螺旋桿菌檢測)", ("urease test", "urea breath test", "H. pylori", "幽門螺旋桿菌檢測"), "H. pylori 可用侵入性或非侵入性檢測確認。"),
    TopicSeed("diagnostic", "esophageal-ph-monitoring", "Esophageal pH monitoring (食道酸鹼監測)", ("24-hour ph", "pH monitoring", "食道酸鹼", "Bernstein"), "GERD 疑似但內視鏡正常時可量化酸暴露。"),
    TopicSeed("diagnostic", "stool-osmotic-gap", "Stool osmotic gap (糞便滲透壓差)", ("stool osmotic gap", "糞便滲透壓", "osmotic diarrhea", "secretory diarrhea"), "協助區分滲透性與分泌性腹瀉。"),
    TopicSeed("diagnostic", "liver-function-tests", "Liver function tests, LFTs (肝功能檢查)", ("肝功能檢查", "LFT", "AST", "ALT", "ALP", "GGT", "bilirubin"), "用 AST/ALT、ALP/GGT、bilirubin、albumin、PT/INR 判斷肝膽疾病型態與功能。"),
    TopicSeed("diagnostic", "viral-hepatitis-serology", "Viral hepatitis serology (病毒性肝炎血清學)", ("HBsAg", "anti-HBs", "anti-HBc", "HBeAg", "anti-HCV", "IgM anti-HAV", "病毒性肝炎血清"), "用血清標記判讀 HAV/HBV/HCV 等感染狀態、免疫與傳染性。"),
    TopicSeed("diagnostic", "serum-ascites-albumin-gradient", "Serum-ascites albumin gradient, SAAG (血清腹水白蛋白梯度)", ("SAAG", "serum-ascites albumin gradient", "血清腹水白蛋白"), "SAAG 協助判斷腹水是否與門脈高壓相關。"),
    TopicSeed("diagnostic", "ascitic-fluid-analysis", "Ascitic fluid analysis (腹水分析)", ("腹水分析", "ascitic fluid", "PMN", "腹水白血球"), "腹水細胞數、白蛋白、蛋白與培養用於診斷 SBP 與腹水成因。"),
    TopicSeed("diagnostic", "child-pugh-score", "Child-Pugh score (Child-Pugh 分級)", ("Child", "Child-Pugh", "Child's classification"), "以 bilirubin、albumin、PT/INR、ascites、encephalopathy 評估肝硬化嚴重度。"),
    TopicSeed("diagnostic", "meld-score", "MELD score (MELD 分數)", ("MELD", "model for end-stage liver disease"), "以 bilirubin、INR、creatinine 等估計末期肝病預後與移植優先度。"),
    TopicSeed("diagnostic", "thyroid-function-tests", "Thyroid function tests (甲狀腺功能檢查)", ("TSH", "free T4", "T3", "甲狀腺功能"), "TSH、free T4/T3 是甲狀腺亢進或低下的核心檢查。"),
    TopicSeed("diagnostic", "thyroid-fine-needle-aspiration", "Thyroid fine-needle aspiration, FNA (甲狀腺細針抽吸)", ("FNA", "fine needle", "細針抽吸"), "甲狀腺結節依超音波風險與大小決定 FNA。"),
    TopicSeed("diagnostic", "oral-glucose-tolerance-test", "Oral glucose tolerance test, OGTT (口服葡萄糖耐受試驗)", ("OGTT", "oral glucose tolerance", "口服葡萄糖耐受"), "用於診斷糖尿病、糖尿病前期與妊娠糖尿病。"),
    TopicSeed("diagnostic", "hba1c", "Hemoglobin A1c, HbA1c (糖化血色素)", ("HbA1c", "A1C", "糖化血色素"), "反映近期平均血糖並作為糖尿病診斷與控制目標。"),
    TopicSeed("diagnostic", "c-peptide", "C-peptide (C 胜肽)", ("C peptide", "C-peptide", "C 胜肽"), "反映內生性胰島素分泌，可協助分辨糖尿病型態。"),
    TopicSeed("diagnostic", "dexamethasone-suppression-test", "Dexamethasone suppression test (地塞米松抑制試驗)", ("dexamethasone suppression", "地塞米松抑制"), "篩檢或評估 Cushing syndrome 的 HPA axis 回饋。"),
    TopicSeed("diagnostic", "acth-stimulation-test", "ACTH stimulation test (ACTH 刺激試驗)", ("ACTH stimulation", "cosyntropin", "Synacthen", "ACTH 刺激"), "評估腎上腺皮質醇分泌能力。"),
    TopicSeed("diagnostic", "water-deprivation-test", "Water deprivation test (禁水試驗)", ("water deprivation", "禁水試驗"), "用於區分中樞性 DI、腎因性 DI 與 primary polydipsia。"),
    TopicSeed("diagnostic", "bone-mineral-density", "Bone mineral density, BMD (骨密度檢查)", ("DEXA", "BMD", "bone mineral density", "骨密度"), "骨質疏鬆診斷與骨折風險評估常用檢查。"),
    # Drugs.
    TopicSeed("drug", "proton-pump-inhibitors", "Proton pump inhibitors, PPI (質子幫浦抑制劑)", ("PPI", "proton pump inhibitor", "omeprazole", "esomeprazole", "質子幫浦"), "抑制胃酸分泌，用於 GERD、消化性潰瘍與部分上消化道出血情境。"),
    TopicSeed("drug", "h2-receptor-antagonists", "H2 receptor antagonists (H2 受體拮抗劑)", ("H2 blocker", "H2 receptor", "famotidine", "ranitidine"), "抑制胃酸分泌，可用於 GERD 或潰瘍相關症狀控制。"),
    TopicSeed("drug", "antacids", "Antacids (制酸劑)", ("Antacids", "制酸劑"), "中和胃酸，用於短期緩解胃酸相關症狀。"),
    TopicSeed("drug", "prokinetic-agents", "Prokinetic agents (促腸胃蠕動藥)", ("Prokinetic", "Metoclopramide", "Domperidone", "Cisapride"), "促進胃腸蠕動或提高 LES 壓力，部分用於 GERD 或胃排空問題。"),
    TopicSeed("drug", "lactulose", "Lactulose (乳果糖)", ("lactulose", "乳果糖"), "酸化腸道並促進排便，用於 hepatic encephalopathy 治療。"),
    TopicSeed("drug", "rifaximin", "Rifaximin (利福昔明)", ("rifaximin", "Rifaximin", "利福昔明", "neomycin", "metronidazole"), "降低腸道產氨菌負荷，可作為 hepatic encephalopathy 輔助治療。"),
    TopicSeed("drug", "somatostatin-analogs", "Somatostatin analogs (Somatostatin 類藥物)", ("somatostatin", "octreotide", "Somatostatin"), "降低門脈血流，可用於急性靜脈曲張出血處置。"),
    TopicSeed("drug", "terlipressin", "Terlipressin (特利加壓素)", ("terlipressin", "Terlipressin", "特利加壓素"), "血管收縮藥物，可用於肝腎症候群或靜脈曲張出血情境。"),
    TopicSeed("drug", "metformin", "Metformin (二甲雙胍)", ("Metformin", "metformin", "二甲雙胍"), "第 2 型糖尿病常用一線藥物，可降低肝糖輸出並改善胰島素阻抗。"),
    TopicSeed("drug", "sulfonylureas", "Sulfonylureas (磺醯脲類)", ("Sulfonylurea", "Glimepiride", "Glibenclamide", "磺醯脲"), "促進胰島素分泌，降糖效果明顯但有低血糖與體重增加風險。"),
    TopicSeed("drug", "insulin", "Insulin (胰島素)", ("Insulin", "insulin", "胰島素"), "治療第 1 型糖尿病、住院高血糖、DKA/HHS 或部分第 2 型糖尿病的重要藥物。"),
    TopicSeed("drug", "sglt2-inhibitors", "SGLT2 inhibitors (SGLT2 抑制劑)", ("SGLT2", "gliflozin", "Empagliflozin", "Dapagliflozin"), "促進尿糖排泄的降糖藥，兼具心腎保護證據但需注意酮酸中毒等風險。"),
    TopicSeed("drug", "glp1-receptor-agonists", "GLP-1 receptor agonists (GLP-1 受體促效劑)", ("GLP-1", "liraglutide", "semaglutide", "exenatide"), "腸泌素類藥物，促進葡萄糖依賴性胰島素分泌並有減重效果。"),
    TopicSeed("drug", "dpp4-inhibitors", "DPP-4 inhibitors (DPP-4 抑制劑)", ("DPP-4", "sitagliptin", "linagliptin", "vildagliptin"), "延長內生性 incretin 作用的口服降糖藥。"),
    TopicSeed("drug", "thiazolidinediones", "Thiazolidinediones, TZD (Thiazolidinedione 類)", ("TZD", "Thiazolidinedione", "Pioglitazone", "Rosiglitazone"), "PPAR-gamma agonist，改善胰島素阻抗但需注意水腫、心衰竭與骨折等風險。"),
    TopicSeed("drug", "alpha-glucosidase-inhibitors", "Alpha-glucosidase inhibitors (α-葡萄糖苷酶抑制劑)", ("Acarbose", "alpha-glucosidase", "α-glucosidase"), "延緩碳水化合物吸收，主要降低餐後血糖。"),
    TopicSeed("drug", "levothyroxine", "Levothyroxine (左旋甲狀腺素)", ("Levothyroxine", "L-thyroxine", "左旋甲狀腺素"), "甲狀腺低下替代治療核心藥物。"),
    TopicSeed("drug", "antithyroid-drugs", "Antithyroid drugs (抗甲狀腺藥物)", ("Methimazole", "Propylthiouracil", "PTU", "抗甲狀腺"), "抑制甲狀腺素合成，用於甲狀腺亢進或 thyroid storm 特定階段。"),
    TopicSeed("drug", "bisphosphonates", "Bisphosphonates (雙磷酸鹽類)", ("Bisphosphonate", "Alendronate", "雙磷酸"), "抑制骨吸收，用於骨質疏鬆治療。"),
    # Procedures.
    TopicSeed("procedure", "endoscopic-band-ligation", "Endoscopic band ligation (內視鏡靜脈曲張結紮)", ("band ligation", "內視鏡結紮", "ligation"), "食道靜脈曲張出血與預防再出血的重要內視鏡治療。"),
    TopicSeed("procedure", "endoscopic-sclerotherapy", "Endoscopic sclerotherapy (內視鏡硬化劑注射)", ("sclerotherapy", "硬化劑", "cyanoacrylate", "Histoacryl"), "靜脈曲張或特定出血病灶的內視鏡注射治療。"),
    TopicSeed("procedure", "paracentesis", "Paracentesis (腹水穿刺)", ("paracentesis", "腹水穿刺", "大量腹水放液"), "用於腹水診斷、SBP 評估與大量腹水治療。"),
    TopicSeed("procedure", "transjugular-intrahepatic-portosystemic-shunt", "Transjugular intrahepatic portosystemic shunt, TIPS (經頸靜脈肝內門體分流)", ("TIPS", "transjugular intrahepatic", "門體分流"), "以介入方式降低門脈壓，可用於選定的靜脈曲張出血或難治性腹水。"),
    TopicSeed("procedure", "liver-transplantation", "Liver transplantation (肝臟移植)", ("肝臟移植", "liver transplantation", "liver transplant"), "末期肝病、部分 HCC 或肝衰竭的根本治療選項。"),
    TopicSeed("procedure", "ercp", "Endoscopic retrograde cholangiopancreatography, ERCP (內視鏡逆行性膽胰管攝影)", ("ERCP", "endoscopic retrograde", "逆行性膽胰管"), "診斷與治療膽胰管阻塞、結石或膽管炎的重要內視鏡程序。"),
    TopicSeed("procedure", "cholecystectomy", "Cholecystectomy (膽囊切除術)", ("膽囊切除", "cholecystectomy"), "症狀性膽結石或急性膽囊炎常見手術治療。"),
    TopicSeed("procedure", "radioactive-iodine-therapy", "Radioactive iodine therapy (放射性碘治療)", ("radioactive iodine", "RAI", "放射性碘"), "用於部分甲狀腺亢進與甲狀腺癌治療。"),
    # Guideline/criteria.
    TopicSeed("guideline", "ncep-atp3-metabolic-syndrome-criteria", "NCEP ATP III metabolic syndrome criteria (NCEP ATP III 新陳代謝症候群準則)", ("NCEP", "ATP III", "ATPIII", "metabolic syndrome"), "以腰圍、血壓、血糖、TG、HDL 判定 metabolic syndrome。"),
    TopicSeed("guideline", "diabetes-care-targets", "Diabetes care targets (糖尿病照護目標)", ("糖尿病臨床照護指引", "HbA1C < 7", "血糖目標", "LDL-C"), "糖尿病控制目標包含血糖、血壓、血脂與生活型態。"),
    TopicSeed("guideline", "variceal-bleeding-management", "Variceal bleeding management (靜脈曲張出血處置)", ("variceal bleeding", "靜脈曲張出血", "somatostatin", "band ligation"), "急性靜脈曲張出血需結合復甦、血管收縮藥、抗生素與內視鏡治療。"),
    # Physiology/anatomy/concepts.
    TopicSeed("physiology", "lower-esophageal-sphincter-pressure", "Lower esophageal sphincter pressure (下食道括約肌壓力)", ("LES", "下食道括約肌", "lower esophageal sphincter"), "LES 壓力與短暫放鬆決定 GERD 風險，受荷爾蒙、神經、藥物與食物影響。"),
    TopicSeed("physiology", "bilirubin-metabolism", "Bilirubin metabolism (膽紅素代謝)", ("bilirubin metabolism", "膽紅素", "unconjugated", "conjugated"), "膽紅素生成、肝攝取、結合與膽汁排泄異常造成不同型態黃疸。"),
    TopicSeed("physiology", "enterohepatic-circulation", "Enterohepatic circulation (腸肝循環)", ("enterohepatic", "腸肝循環", "bile acid"), "膽汁酸與部分物質在肝膽腸之間循環。"),
    TopicSeed("physiology", "glucose-homeostasis", "Glucose homeostasis (血糖恆定)", ("血糖恆定", "glucose homeostasis", "insulin", "glucagon"), "胰島素、升糖素、肝糖輸出、肌肉與脂肪組織共同維持血糖。"),
    TopicSeed("physiology", "insulin-resistance", "Insulin resistance (胰島素阻抗)", ("胰島素阻抗", "insulin resistance"), "胰島素作用下降連結第 2 型糖尿病、代謝症候群、脂肪肝與心血管風險。"),
    TopicSeed("physiology", "hpa-axis", "Hypothalamic-pituitary-adrenal axis, HPA axis (下視丘-腦垂體-腎上腺軸)", ("HPA", "CRH", "ACTH", "cortisol"), "HPA axis 調控皮質醇分泌，與 Cushing syndrome、adrenal insufficiency 檢測相關。"),
    TopicSeed("physiology", "hpt-axis", "Hypothalamic-pituitary-thyroid axis, HPT axis (下視丘-腦垂體-甲狀腺軸)", ("HPT", "TRH", "TSH", "thyroxine"), "HPT axis 調控甲狀腺素，TSH/free T4 是判讀核心。"),
    TopicSeed("physiology", "calcium-homeostasis", "Calcium homeostasis (鈣離子恆定)", ("鈣離子平衡", "calcium homeostasis", "PTH", "vitamin D", "calcitonin"), "PTH、vitamin D、腎臟、腸道與骨骼共同維持鈣磷平衡。"),
    TopicSeed("anatomy", "esophagus", "Esophagus (食道)", ("食道", "esophagus", "LES"), "食道連結口咽與胃，疾病包含吞嚥困難、GERD、Barrett esophagus 與癌症。"),
    TopicSeed("anatomy", "stomach", "Stomach (胃)", ("胃", "stomach", "gastric"), "胃酸分泌、黏膜保護與幽門螺旋桿菌相關疾病是消化內科核心。"),
    TopicSeed("anatomy", "small-intestine", "Small intestine (小腸)", ("小腸", "small intestine", "duodenum", "jejunum", "ileum"), "小腸負責吸收並涉及腹瀉、IBD、吸收不良等疾病。"),
    TopicSeed("anatomy", "colon", "Colon (大腸)", ("大腸", "colon", "colitis"), "大腸疾病包含 IBD、感染性腸炎、出血與腫瘤。"),
    TopicSeed("anatomy", "liver", "Liver (肝臟)", ("肝臟", "liver", "hepatocyte"), "肝臟負責代謝、解毒、合成蛋白與膽汁生成。"),
    TopicSeed("anatomy", "biliary-tract", "Biliary tract (膽道系統)", ("膽道", "biliary", "gallbladder", "膽囊", "總膽管"), "膽囊與膽管系統相關疾病包含結石、膽囊炎、膽管炎與阻塞性黃疸。"),
    TopicSeed("anatomy", "pancreas", "Pancreas (胰臟)", ("胰臟", "pancreas", "pancreatic"), "胰臟兼具外分泌消化酵素與內分泌血糖調控功能。"),
    TopicSeed("anatomy", "pituitary-gland", "Pituitary gland (腦垂體)", ("腦垂體", "pituitary"), "腦垂體調控多條內分泌軸，病變可造成過量、低下或壓迫。"),
    TopicSeed("anatomy", "thyroid-gland", "Thyroid gland (甲狀腺)", ("甲狀腺", "thyroid"), "甲狀腺分泌 T4/T3，調控代謝與多器官功能。"),
    TopicSeed("anatomy", "adrenal-gland", "Adrenal gland (腎上腺)", ("腎上腺", "adrenal"), "腎上腺皮質與髓質分泌 glucocorticoid、mineralocorticoid、androgen 與 catecholamine。"),
    TopicSeed("anatomy", "parathyroid-glands", "Parathyroid glands (副甲狀腺)", ("副甲狀腺", "parathyroid"), "副甲狀腺分泌 PTH，調控鈣磷平衡。"),
)

ALL_SEEDS: tuple[TopicSeed, ...] = SEEDS + SECOND_BOOK_SEEDS


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "untitled"


def clean_text(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\{[0-9]+\}-+\n?", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def display_chapter_title(path: Path) -> str:
    first_line = path.read_text(encoding="utf-8", errors="ignore").splitlines()[0].strip()
    if first_line.startswith("#"):
        return first_line.lstrip("#").strip()
    stem = path.stem
    return stem.split("_")[-1]


def chapter_files(book_dir: Path) -> list[Path]:
    full_book = book_dir / f"{book_dir.name}.md"
    files = sorted(book_dir.glob("*.md"))
    return [path for path in files if path != full_book]


def wiki_link(path: Path, label: str | None = None) -> str:
    rel = path.relative_to(WIKI).with_suffix("").as_posix()
    if label:
        return f"[[{rel}|{label}]]"
    return f"[[{rel}]]"


def source_slug(book_key: str, index: int) -> str:
    return f"{book_key}-ch{index:02d}"


def source_page_path(slug: str) -> Path:
    return WIKI / "sources" / f"{slug}.md"


def seed_page_path(seed: TopicSeed) -> Path:
    return WIKI / TYPE_DIR[seed.kind] / f"{seed.slug}.md"


def extract_headings(text: str) -> list[str]:
    headings: list[str] = []
    for match in re.finditer(r"^#{2,6}\s+(.+)$", text, flags=re.MULTILINE):
        heading = re.sub(r"^[A-Z甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥0-9IVXivx]+[.、)]\s*", "", match.group(1).strip())
        heading = heading.strip(":： ")
        if not heading or heading in headings:
            continue
        if heading in GENERIC_HEADINGS:
            continue
        if heading == "題目" or heading.startswith("題目"):
            continue
        headings.append(heading)
    return headings


def find_mentions(text: str, seed: TopicSeed, limit: int = 5) -> list[str]:
    cleaned = clean_text(text)
    paragraphs = re.split(r"\n\s*\n|(?=^####\s+)|(?=^- )", cleaned, flags=re.MULTILINE)
    mentions: list[str] = []
    patterns = []
    for keyword in seed.keywords:
        keyword = keyword.strip()
        if len(keyword) < 2:
            continue
        escaped = re.escape(keyword)
        if re.fullmatch(r"[A-Za-z0-9]{2,5}", keyword):
            escaped = rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
        patterns.append(escaped)
    if not patterns:
        return mentions
    pattern = re.compile("|".join(patterns), flags=re.IGNORECASE)
    for para in paragraphs:
        para = re.sub(r"\s+", " ", para).strip()
        if len(para) < 20:
            continue
        if pattern.search(para):
            para = para.strip("- ")
            if len(para) > 360:
                hit = pattern.search(para)
                start = max(0, (hit.start() if hit else 0) - 120)
                end = min(len(para), (hit.end() if hit else 0) + 220)
                para = para[start:end].strip()
                if start:
                    para = "..." + para
                if end < len(para):
                    para = para + "..."
            if para not in mentions:
                mentions.append(para)
        if len(mentions) >= limit:
            break
    return mentions


def source_summary(path: Path, slug: str, title: str, book_name: str, order: int, matched: list[TopicSeed]) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    headings = extract_headings(raw)
    key_headings = [h for h in headings[:12] if h != title]
    topic_links = [wiki_link(seed_page_path(seed), seed.title) for seed in matched[:60]]
    if not topic_links:
        topic_links = ["尚未擷取 topic node。"]
    scope_items = "\n".join(f"- {h}" for h in key_headings[:10]) or "- 本章以原始章節內容為範圍。"
    topic_items = "\n".join(f"- {link}" for link in topic_links)
    source_rel = path.relative_to(ROOT).as_posix()
    return f"""---
type: source
status: draft
created: {TODAY}
updated: {TODAY}
source_file: {source_rel}
book: {book_name}
chapter_order: {order}
sources: []
tags:
  - medicine
  - source
  - textbook
---

# {title}

## Source Metadata

- Book: {book_name}
- Chapter file: `{source_rel}`
- Ingest mode: chapter-split markdown, topic-first extraction.

## Scope and Reliability

此頁是 textbook chapter 的來源摘要，用來支撐 topic pages。原始檔含 OCR/版面轉換痕跡、表格與考題；臨床 guideline、drug dosing、急症處置仍需以最新版官方來源複核。

## Chapter Scope

{scope_items}

## Extracted Topic Nodes

{topic_items}

## Clinical Caveats

- 此章內容屬讀書整理來源，不等同個人醫療建議。
- 若涉及 dosing、禁忌、pregnancy/lactation、renal/hepatic adjustment、急症處置或當代 guideline，回答時需再查 current official source。

## Open Questions

- 哪些 topic pages 需要與新版 guideline 或藥品仿單交叉更新？
"""


def source_relevance(seed: TopicSeed, item: tuple[str, Path, list[str]]) -> tuple[int, str]:
    chapter_title, source_path, snippets = item
    title_haystack = chapter_title.lower()
    snippet_haystack = " ".join(snippets[:2]).lower()
    score = len(snippets)
    for keyword in seed.keywords:
        keyword_l = keyword.lower()
        if keyword_l and keyword_l in title_haystack:
            score += 100
        if keyword_l and keyword_l in snippet_haystack:
            score += 5
    return (-score, source_path.name)


def existing_topic_parts(path: Path) -> tuple[list[str], list[str], str]:
    if not path.exists():
        return [], [], TODAY
    text = path.read_text(encoding="utf-8", errors="ignore")
    sources_section = ""
    match_sources = re.search(r"## Source Coverage\n\n(.*?)(?=\n## Key Details From Sources)", text, flags=re.S)
    if match_sources:
        sources_section = match_sources.group(1)
    raw_sources = re.findall(r"\[\[(sources/[^\]|#]+)(?:[^\]]*)\]\]", sources_section)
    sources = [f"[[{source}]]" for source in dict.fromkeys(raw_sources)]
    details: list[str] = []
    match = re.search(r"## Key Details From Sources\n\n(.*?)(?=\n## Clinical Caveats)", text, flags=re.S)
    if match:
        for line in match.group(1).splitlines():
            if line.startswith("- "):
                details.append(line)
    created_match = re.search(r"^created:\s*([0-9-]+)", text, flags=re.M)
    created = created_match.group(1) if created_match else TODAY
    return sources, details, created


def topic_page(seed: TopicSeed, source_mentions: list[tuple[str, Path, list[str]]], available_slugs: set[str], book_name: str) -> str:
    path = seed_page_path(seed)
    prior_sources, prior_details, created = existing_topic_parts(path)
    source_mentions = sorted(source_mentions, key=lambda item: source_relevance(seed, item))
    source_links = prior_sources + [wiki_link(source_path) for _, source_path, _ in source_mentions]
    source_links = list(dict.fromkeys(source_links))
    tag = TYPE_DIR[seed.kind][:-1] if TYPE_DIR[seed.kind].endswith("s") else TYPE_DIR[seed.kind]
    aliases = [seed.title]
    english = seed.title.split("(")[0].strip()
    zh_match = re.search(r"\(([^)]+)\)", seed.title)
    if english and english != seed.title:
        aliases.append(english)
    if zh_match:
        aliases.append(zh_match.group(1).strip())
    aliases_yaml = "\n".join(f"  - {alias!r}" for alias in dict.fromkeys(aliases))
    sources_yaml = "\n".join(f"  - \"{link}\"" for link in source_links) or "  - []"
    coverage = "\n".join(f"- {link}" for link in source_links) or "- 尚無來源連結。"
    bullets: list[str] = []
    for chapter_title, source_path, snippets in source_mentions:
        for snippet in snippets[:3]:
            bullets.append(f"- {snippet} Source: {wiki_link(source_path, chapter_title)}.")
            if len(bullets) >= 10:
                break
        if len(bullets) >= 10:
            break
    combined_details = list(dict.fromkeys(bullets + prior_details))
    detail = "\n".join(combined_details[:18]) or "- 尚未擷取到足夠片段。"
    related = related_links(seed, available_slugs)
    related_block = "\n".join(f"- {link}" for link in related) if related else "- 待補。"
    return f"""---
type: {seed.kind}
status: draft
created: {created}
updated: {TODAY}
sources:
{sources_yaml}
aliases:
{aliases_yaml}
tags:
  - medicine
  - {tag}
  - auto-topic-node
---

# {seed.title}

## Summary

{seed.summary} 本頁已整合至 `{book_name}`；若同一 topic 也出現在舊來源，來源與重點會保留並合併。

## Source Coverage

{coverage}

## Key Details From Sources

{detail}

## Clinical Caveats

- 本頁是 textbook-derived study note，不可直接作為診療、處方或急症處置依據。
- 若問題涉及 current guideline、drug dosing、禁忌、pregnancy/lactation、兒科、renal/hepatic adjustment 或高風險處置，需查最新版官方來源。

## Related Pages

{related_block}

## Follow-up

- 後續可補上 guideline 年份、治療流程圖、diagnostic criteria 表格與藥物安全監測整理。
"""


def related_links(seed: TopicSeed, available_slugs: set[str]) -> list[str]:
    groups = {
        "heart-failure": ["hfref", "hfpef", "bnp", "ace-inhibitors", "beta-blockers", "loop-diuretics", "nyha-functional-class", "acc-aha-heart-failure-stages"],
        "acute-coronary-syndrome": ["unstable-angina", "nstemi", "stemi", "electrocardiography", "cardiac-biomarkers", "antiplatelet-therapy", "heparin", "percutaneous-coronary-intervention"],
        "asthma": ["bronchodilator-reversibility-test", "methacholine-provocation-test", "inhaled-corticosteroids", "laba", "saba", "gina-asthma-step-therapy", "airway-inflammation"],
        "copd": ["pulmonary-function-test", "lama", "laba", "gold-copd-assessment", "oxygen-therapy", "noninvasive-ventilation"],
        "pulmonary-embolism": ["wells-score", "d-dimer", "ct-pulmonary-angiography", "anticoagulation", "pulmonary-hypertension"],
        "pleural-effusion": ["light-criteria", "thoracentesis", "pleura", "empyema"],
        "lung-cancer": ["non-small-cell-lung-cancer", "small-cell-lung-cancer", "lung-cancer-staging", "bronchoscopy"],
        "infective-endocarditis": ["duke-criteria", "echocardiography", "heart-valves"],
        "gastroesophageal-reflux-disease": ["lower-esophageal-sphincter-pressure", "proton-pump-inhibitors", "h2-receptor-antagonists", "esophageal-ph-monitoring", "barrett-esophagus"],
        "peptic-ulcer-disease": ["helicobacter-pylori-infection", "helicobacter-pylori-testing", "proton-pump-inhibitors", "upper-gastrointestinal-bleeding"],
        "upper-gastrointestinal-bleeding": ["upper-endoscopy", "peptic-ulcer-disease", "esophageal-varices", "variceal-bleeding-management", "somatostatin-analogs"],
        "liver-cirrhosis": ["portal-hypertension", "ascites", "hepatic-encephalopathy", "hepatorenal-syndrome", "child-pugh-score", "meld-score", "liver-transplantation"],
        "ascites": ["serum-ascites-albumin-gradient", "ascitic-fluid-analysis", "spontaneous-bacterial-peritonitis", "paracentesis", "transjugular-intrahepatic-portosystemic-shunt"],
        "hepatitis-b": ["viral-hepatitis-serology", "hepatocellular-carcinoma", "liver-cirrhosis"],
        "hepatitis-c": ["viral-hepatitis-serology", "hepatocellular-carcinoma", "liver-cirrhosis"],
        "diabetes-mellitus": ["type-1-diabetes", "type-2-diabetes", "hba1c", "oral-glucose-tolerance-test", "insulin", "metformin", "diabetic-ketoacidosis", "hyperosmolar-hyperglycemic-state"],
        "type-2-diabetes": ["insulin-resistance", "metabolic-syndrome", "metformin", "sglt2-inhibitors", "glp1-receptor-agonists", "diabetes-care-targets"],
        "hyperthyroidism": ["graves-disease", "thyroid-function-tests", "antithyroid-drugs", "radioactive-iodine-therapy", "thyroid-storm"],
        "hypothyroidism": ["hashimoto-thyroiditis", "thyroid-function-tests", "levothyroxine"],
        "cushing-syndrome": ["hpa-axis", "dexamethasone-suppression-test"],
        "adrenal-insufficiency": ["hpa-axis", "acth-stimulation-test", "systemic-corticosteroids"],
        "hyperparathyroidism": ["calcium-homeostasis", "hypercalcemia", "bone-mineral-density"],
        "osteoporosis": ["calcium-homeostasis", "bone-mineral-density", "bisphosphonates"],
    }
    slug_to_seed = {item.slug: item for item in ALL_SEEDS}
    rel_slugs = set(groups.get(seed.slug, []))
    for anchor, values in groups.items():
        if seed.slug in values:
            rel_slugs.add(anchor)
    links: list[str] = []
    for slug in sorted(rel_slugs):
        if slug not in available_slugs:
            continue
        other = slug_to_seed.get(slug)
        if other:
            links.append(wiki_link(seed_page_path(other), other.title))
    return links


def category_index(kind: str, seeds: list[TopicSeed]) -> str:
    title = TYPE_DIR[kind].replace("-", " ").title()
    noun = {
        "condition": "Diseases and syndromes",
        "drug": "Medications, drug classes, pharmacology, contraindications, and monitoring",
        "diagnostic": "Labs, imaging, criteria, scoring systems, and test interpretation",
        "procedure": "Clinical procedures, operations, interventions, and workflows",
        "guideline": "Guideline pages and recommendation frameworks",
        "physiology": "Normal function and pathways",
        "anatomy": "Organs, structures, and regions",
        "concept": "Mechanisms, definitions, and frameworks",
    }[kind]
    lines = [f"- {wiki_link(seed_page_path(seed), seed.title)} - {seed.summary}" for seed in sorted(seeds, key=lambda s: s.slug)]
    body = "\n".join(lines) or "- No pages yet."
    return f"""---
type: index
status: draft
created: 2026-06-07
updated: {TODAY}
sources: []
tags:
  - medicine
  - index
---

# {title} Index

{noun}.

## Pages

{body}
"""


def sources_index(source_paths: list[Path]) -> str:
    lines = []
    for path in source_paths:
        title = path.stem
        if path.exists():
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("# "):
                    title = line.lstrip("# ").strip()
                    break
        lines.append(f"- {wiki_link(path, title or path.stem)}")
    body = "\n".join(lines) or "- No source summaries yet."
    return f"""---
type: index
status: draft
created: 2026-06-07
updated: {TODAY}
sources: []
tags:
  - medicine
  - index
---

# Sources Index

Source summaries catalog.

## Textbook Chapters

{body}
"""


def main_index(counts: dict[str, int], book_name: str) -> str:
    cat_lines = "\n".join(
        f"- [[{TYPE_DIR[kind]}/index|{TYPE_DIR[kind].title()}]] - {count} topic pages"
        for kind, count in counts.items()
        if count
    )
    return f"""---
type: index
status: draft
created: 2026-06-07
updated: {TODAY}
sources: []
tags:
  - medicine
  - index
---

# Index

Content catalog for this medical LLM wiki. Update this file on every ingest, durable query, or maintenance pass.

## Core Pages

- [[overview]] - Top-level map and current synthesis of the vault.
- [[log]] - Append-only chronology of ingests, queries, lints, and maintenance.

## Sources

- [[sources/index]] - Source summaries catalog. Latest ingest: `{book_name}`.

## Topic Categories

{cat_lines}

## Questions

- [[questions/index]] - Durable answers filed from useful queries.

## Maintenance Notes

- Latest textbook ingested topic-first on {TODAY}: `{book_name}`.
- Topic nodes are organized by medical entity or concept, not chapter title. Source chapter pages remain only as citation anchors.
"""


def overview(book_name: str, latest_source_count: int, total_source_count: int, topic_count: int) -> str:
    return f"""---
type: overview
status: draft
created: 2026-06-07
updated: {TODAY}
sources: []
tags:
  - medicine
---

# Medical Wiki Overview

此 vault 採 LLM Wiki 模式：`raw/` 是 immutable source，`wiki/` 是 Codex 維護的知識圖譜。

## Current Scope

- Latest ingested textbook: `{book_name}`
- Latest chapter source summaries: {latest_source_count}
- Total chapter source summaries: {total_source_count}
- Total topic-first nodes: {topic_count}

## Graph Shape

Source pages 只作 citation anchors。主要查詢入口應使用 topic nodes：conditions、drugs、diagnostics、procedures、guidelines、physiology、anatomy、concepts。

## Safety Note

此 vault 是讀書與知識管理工具，不是 clinical decision system。涉及 current guideline、drug dosing、禁忌、孕哺、兒科、renal/hepatic adjustment 或急症處置時，需再查官方最新版來源。
"""


def link_check() -> tuple[int, list[str]]:
    files = [p for p in WIKI.rglob("*.md") if "templates" not in p.relative_to(WIKI).parts]
    all_files = [p for p in WIKI.rglob("*.md")]
    basenames: dict[str, Path] = {p.stem: p for p in all_files}
    rels: set[str] = {p.relative_to(WIKI).with_suffix("").as_posix() for p in all_files}
    missing: list[str] = []
    pattern = re.compile(r"\[\[([^\]|#]+)")
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for target in pattern.findall(text):
            target = target.strip()
            if target in rels or target in basenames:
                continue
            missing.append(f"{path.relative_to(ROOT)} -> [[{target}]]")
    return len(files), missing


def health_report(book_name: str, source_count: int, matched_seeds: list[TopicSeed], category_counts: dict[str, int]) -> str:
    files_checked, missing = link_check()
    counts = "\n".join(f"- {TYPE_DIR[kind]}: {count}" for kind, count in category_counts.items() if count)
    missing_block = "\n".join(f"- {item}" for item in missing[:50]) if missing else "- None."
    status = "PASS" if not missing else "WARN"
    return f"""# Health Check - {book_name}

Date: {TODAY}
Status: {status}

## Scope

- Source chapter pages created/updated: {source_count}
- Topic nodes created/updated in this pass: {len(matched_seeds)}
- Wiki files checked for links: {files_checked}
- Missing wiki links: {len(missing)}

## Total Topic Counts

{counts}

## Link Check

{missing_block}

## Notes

- This pass used deterministic keyword extraction plus curated topic seeds for the current textbook domain.
- Existing topic pages were preserved and updated when the current textbook overlapped prior knowledge.
- Topic pages are disease/treatment/guideline/drug/diagnostic/procedure/physiology/anatomy/concept nodes, not chapter-title buckets.
- Content is Mandarin-first with English medical terms included in titles and aliases where available.
- Guideline-sensitive and dosing-sensitive claims remain textbook-derived and need current official verification before clinical use.

## Recommended Next Lint

- Merge duplicate Chinese/English aliases if Obsidian graph shows separate nodes.
- Promote high-yield, frequently queried pages from auto-extracted notes into manually synthesized review pages.
"""


def append_log(book_name: str, source_count: int, topic_count: int) -> None:
    log_path = WIKI / "log.md"
    if not log_path.exists():
        log_path.write_text(
            f"""---
type: log
status: draft
created: {TODAY}
updated: {TODAY}
sources: []
tags:
  - medicine
  - log
---

# Log

Append-only chronological activity log.
""",
            encoding="utf-8",
        )
    header = f"## [{TODAY}] ingest | {book_name}"
    text = log_path.read_text(encoding="utf-8", errors="ignore")
    if header in text:
        return
    entry = f"""

{header}

- Ingested {source_count} chapter-split markdown files.
- Created/updated {topic_count} topic-first medical nodes across conditions, drugs, diagnostics, procedures, guidelines, physiology, anatomy, and concepts.
- Updated `wiki/index.md`, category indexes, `wiki/sources/index.md`, and health-check report.
"""
    log_path.write_text(text.rstrip() + entry + "\n", encoding="utf-8")


def run(book_name: str, book_key: str) -> None:
    book_dir = RAW_BOOKS / book_name
    if not book_dir.exists():
        raise SystemExit(f"Book folder not found: {book_dir}")
    for directory in [WIKI / d for d in TYPE_DIR.values()] + [WIKI / "sources", ROOT / "docs"]:
        directory.mkdir(parents=True, exist_ok=True)

    chapters = chapter_files(book_dir)
    chapter_texts: list[tuple[int, Path, str, str]] = []
    for idx, path in enumerate(chapters, start=1):
        chapter_texts.append((idx, path, display_chapter_title(path), path.read_text(encoding="utf-8", errors="ignore")))

    source_paths: dict[Path, Path] = {}
    matched_by_source: dict[Path, list[TopicSeed]] = {path: [] for _, path, _, _ in chapter_texts}
    mentions_by_seed: dict[TopicSeed, list[tuple[str, Path, list[str]]]] = {}

    for seed in ALL_SEEDS:
        source_mentions: list[tuple[str, Path, list[str]]] = []
        for idx, raw_path, chapter_title, raw_text in chapter_texts:
            mentions = find_mentions(raw_text, seed)
            if mentions:
                source_path = source_page_path(source_slug(book_key, idx))
                source_mentions.append((chapter_title, source_path, mentions))
                matched_by_source[raw_path].append(seed)
        if source_mentions:
            mentions_by_seed[seed] = source_mentions

    for idx, raw_path, chapter_title, _ in chapter_texts:
        slug = source_slug(book_key, idx)
        out = source_page_path(slug)
        out.write_text(source_summary(raw_path, slug, chapter_title, book_name, idx, matched_by_source[raw_path]), encoding="utf-8")
        source_paths[raw_path] = out

    matched_seeds = sorted(mentions_by_seed, key=lambda s: (s.kind, s.slug))
    existing_seed_slugs = {seed.slug for seed in ALL_SEEDS if seed_page_path(seed).exists()}
    available_slugs = existing_seed_slugs | {seed.slug for seed in matched_seeds}
    for seed, source_mentions in mentions_by_seed.items():
        seed_page_path(seed).write_text(topic_page(seed, source_mentions, available_slugs, book_name), encoding="utf-8")

    category_counts: dict[str, int] = {}
    all_existing_seeds = [seed for seed in ALL_SEEDS if seed_page_path(seed).exists()]
    for kind in TYPE_DIR:
        seeds = [seed for seed in all_existing_seeds if seed.kind == kind]
        category_counts[kind] = len(seeds)
        (WIKI / TYPE_DIR[kind] / "index.md").write_text(category_index(kind, seeds), encoding="utf-8")

    source_page_list = sorted(path for path in (WIKI / "sources").glob("*.md") if path.name != "index.md")
    (WIKI / "sources" / "index.md").write_text(sources_index(source_page_list), encoding="utf-8")
    (WIKI / "index.md").write_text(main_index(category_counts, book_name), encoding="utf-8")
    (WIKI / "overview.md").write_text(overview(book_name, len(chapters), len(source_page_list), len(all_existing_seeds)), encoding="utf-8")
    report = health_report(book_name, len(chapters), matched_seeds, category_counts)
    (ROOT / "docs" / f"health-check-{TODAY}-{book_key}.md").write_text(report, encoding="utf-8")
    append_log(book_name, len(chapters), len(matched_seeds))

    print(f"book={book_name}")
    print(f"chapters={len(chapters)}")
    print(f"topic_nodes_updated={len(matched_seeds)}")
    print(f"topic_nodes_total={len(all_existing_seeds)}")
    for kind, count in category_counts.items():
        if count:
            print(f"{TYPE_DIR[kind]}={count}")
    files_checked, missing = link_check()
    print(f"files_checked={files_checked}")
    print(f"missing_links={len(missing)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("book", help="Folder name under raw/books/md")
    parser.add_argument("--book-key", default="med3-book1", help="Stable source slug prefix")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.book, args.book_key)
