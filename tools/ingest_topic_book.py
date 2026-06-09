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
    TopicSeed("condition", "siadh", "SIADH (抗利尿激素分泌不當症候群)", ("SIADH", "抗利尿激素分泌不當"), "ADH 過多造成低鈉血症與濃縮尿。"),
    TopicSeed("condition", "hypopituitarism", "Hypopituitarism (腦垂體功能低下)", ("腦垂體功能低下", "hypopituitarism", "Sheehan"), "腦垂體荷爾蒙缺乏造成多軸內分泌不足。"),
    TopicSeed("condition", "hyperthyroidism", "Hyperthyroidism (甲狀腺亢進)", ("甲狀腺亢進", "hyperthyroidism", "thyrotoxicosis"), "甲狀腺素過多造成高代謝症狀、心悸、體重下降與眼/皮膚表現。"),
    TopicSeed("condition", "graves-disease", "Graves disease (葛瑞夫茲病)", ("Graves", "葛瑞夫", "TSI", "TRAb"), "自體免疫刺激 TSH receptor，是甲狀腺亢進常見原因。"),
    TopicSeed("condition", "hypothyroidism", "Hypothyroidism (甲狀腺低下)", ("甲狀腺低下", "hypothyroidism", "myxedema"), "甲狀腺素不足造成低代謝症狀與 TSH/T4 變化。"),
    TopicSeed("condition", "hashimoto-thyroiditis", "Hashimoto thyroiditis (橋本氏甲狀腺炎)", ("Hashimoto", "橋本", "慢性淋巴球性甲狀腺炎", "anti-TPO", "antithyroglobulin"), "慢性自體免疫甲狀腺炎，是 hypothyroidism 常見原因，可伴其他自體免疫疾病。"),
    TopicSeed("condition", "thyroid-storm", "Thyroid storm (甲狀腺風暴)", ("甲狀腺風暴", "thyroid storm"), "嚴重 thyrotoxicosis 急症，需快速支持與抑制甲狀腺素作用/合成/釋放。"),
    TopicSeed("condition", "thyroid-nodule", "Thyroid nodule (甲狀腺結節)", ("甲狀腺結節", "thyroid nodule", "Solitary thyroid nodule", "cold nodule", "hot nodule"), "甲狀腺結節需以 TSH、ultrasound risk features、FNA 與核醫掃描判斷惡性風險與手術需求。"),
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
    TopicSeed("condition", "diabetic-neuropathy", "Diabetic neuropathy (糖尿病神經病變)", ("糖尿病神經病變", "diabetic neuropathy", "Diabetic neuropathy", "糖尿病神經", "DM Neuropathy"), "糖尿病周邊或自主神經併發症，影響足部照護與生活品質；可為對稱性 distal polyneuropathy 或 focal/cranial neuropathy。"),
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

THIRD_BOOK_SEEDS: tuple[TopicSeed, ...] = (
    # Nephrology: acid-base, electrolytes, kidney syndromes.
    TopicSeed("condition", "metabolic-acidosis", "Metabolic acidosis (代謝性酸中毒)", ("代謝性酸中毒", "Metabolic acidosis", "HCO3 低", "HCO₃ 低"), "HCO3 下降造成酸血症，需依 anion gap、代償與臨床情境找病因。"),
    TopicSeed("condition", "high-anion-gap-metabolic-acidosis", "High anion gap metabolic acidosis (高陰離子間隙代謝性酸中毒)", ("高陰離子間隙代謝", "high anion gap", "HAGMA", "anion gap acidosis"), "未測量陰離子增加造成代謝性酸中毒，常見於乳酸、酮酸、腎衰竭與毒物。"),
    TopicSeed("condition", "normal-anion-gap-metabolic-acidosis", "Normal anion gap metabolic acidosis (正常陰離子間隙代謝性酸中毒)", ("正常陰離子間隙代謝", "normal anion gap", "NAGMA", "hyperchloremic acidosis"), "多與 HCO3 流失或腎排酸障礙相關，常見鑑別為 diarrhea 與 RTA。"),
    TopicSeed("condition", "metabolic-alkalosis", "Metabolic alkalosis (代謝性鹼中毒)", ("代謝性鹼中毒", "Metabolic alkalosis", "HCO3 高", "HCO₃ 高"), "HCO3 上升造成鹼血症，常與體液不足、利尿劑、嘔吐或 mineralocorticoid excess 相關。"),
    TopicSeed("condition", "respiratory-acidosis", "Respiratory acidosis (呼吸性酸中毒)", ("呼吸性酸中毒", "Respiratory acidosis", "PaCO2 高", "hypoventilation"), "換氣不足造成 PaCO2 上升，需分辨急性與慢性腎代償。"),
    TopicSeed("condition", "respiratory-alkalosis", "Respiratory alkalosis (呼吸性鹼中毒)", ("呼吸性鹼中毒", "Respiratory alkalosis", "PaCO2 低", "hyperventilation"), "過度換氣造成 PaCO2 下降，常見於低氧、疼痛、焦慮、敗血症或藥物。"),
    TopicSeed("condition", "renal-tubular-acidosis", "Renal tubular acidosis, RTA (腎小管酸中毒)", ("腎小管酸中毒", "Renal tubular acidosis", "RTA", "distal RTA", "proximal RTA", "Type 4 RTA"), "腎小管排酸或 HCO3 處理異常造成正常陰離子間隙代謝性酸中毒。"),
    TopicSeed("condition", "lactic-acidosis", "Lactic acidosis (乳酸中毒)", ("乳酸中毒", "Lactic acidosis", "lactate"), "組織缺氧、敗血症或藥物等造成 lactate 增加，是高陰離子間隙代謝性酸中毒常見原因。"),
    TopicSeed("condition", "ketoacidosis", "Ketoacidosis (酮酸中毒)", ("酮酸中毒", "Ketoacidosis", "ketone body", "alcoholic ketoacidosis", "starvation ketoacidosis"), "脂肪分解產生 ketone body，可見於糖尿病、酒精或飢餓狀態。"),
    TopicSeed("condition", "toxic-alcohol-poisoning", "Toxic alcohol poisoning (毒性醇中毒)", ("Methanol", "Ethylene glycol", "Isopropanol", "毒性醇", "osmolal gap"), "甲醇、乙二醇等可造成 osmolal gap 與高陰離子間隙代謝性酸中毒。"),
    TopicSeed("condition", "hyponatremia", "Hyponatremia (低血鈉)", ("低血鈉", "Hyponatremia", "血鈉 < 135", "Na 低"), "低血鈉需先排除假性低血鈉，再依滲透壓與體液狀態鑑別。"),
    TopicSeed("condition", "pseudohyponatremia", "Pseudohyponatremia (假性低血鈉)", ("假性低血鈉", "Pseudohyponatremia", "高血脂", "高蛋白", "hyperglycemia"), "血鈉數值下降但需由血糖、血脂、蛋白與血漿滲透壓判斷是否為真正低滲低鈉。"),
    TopicSeed("condition", "syndrome-of-inappropriate-adh-secretion", "SIADH (抗利尿激素不適當分泌症候群)", ("SIADH", "ADH 不適當", "抗利尿激素不適當", "syndrome of inappropriate"), "euvolemic hypotonic hyponatremia 的重要原因，需排除甲狀腺與腎上腺功能不足。"),
    TopicSeed("condition", "osmotic-demyelination-syndrome", "Osmotic demyelination syndrome (滲透性去髓鞘症候群)", ("Central pontine", "CPM", "osmotic demyelination", "橋腦去髓鞘", "矯正太快"), "慢性低血鈉矯正過快可能造成橋腦或橋腦外去髓鞘。"),
    TopicSeed("condition", "hypernatremia", "Hypernatremia (高血鈉)", ("高血鈉", "Hypernatremia", "Na 高", "血鈉 >"), "高血鈉多代表水分相對不足，需依水分流失、鈉負荷與口渴/ADH 軸評估。"),
    TopicSeed("condition", "diabetes-insipidus", "Diabetes insipidus (尿崩症)", ("尿崩症", "Diabetes insipidus", "central DI", "nephrogenic DI", "DDAVP"), "ADH 分泌或腎臟反應不足造成多尿與高血鈉風險。"),
    TopicSeed("condition", "hypokalemia", "Hypokalemia (低血鉀)", ("低血鉀", "Hypokalemia", "K 低", "血鉀 低"), "低血鉀需依攝取、腸胃流失、腎臟流失與 transcellular shift 鑑別。"),
    TopicSeed("condition", "hyperkalemia", "Hyperkalemia (高血鉀)", ("高血鉀", "Hyperkalemia", "K 高", "血鉀 高"), "高血鉀可能造成致命心律不整，需結合 ECG、腎功能、藥物與酸鹼狀態判斷。"),
    TopicSeed("condition", "hypophosphatemia", "Hypophosphatemia (低血磷)", ("低血磷", "Hypophosphatemia", "phosphate 低"), "低血磷可影響肌肉、呼吸與紅血球功能，常與再餵食、酒精、腎流失或細胞內移動相關。"),
    TopicSeed("condition", "hyperphosphatemia", "Hyperphosphatemia (高血磷)", ("高血磷", "Hyperphosphatemia", "phosphate 高"), "高血磷常見於腎功能下降，會影響鈣磷與副甲狀腺軸。"),
    TopicSeed("condition", "acute-kidney-injury", "Acute kidney injury, AKI (急性腎損傷)", ("急性腎損傷", "AKI", "acute kidney injury", "acute renal failure", "急性腎衰竭"), "短期腎功能下降，需分辨 prerenal、intrinsic renal 與 postrenal causes。"),
    TopicSeed("condition", "prerenal-azotemia", "Prerenal azotemia (腎前性氮血症)", ("腎前性", "Prerenal", "有效血液容量", "FENa"), "腎灌流不足造成腎功能下降，早期可逆但可進展為 ATN。"),
    TopicSeed("condition", "acute-tubular-necrosis", "Acute tubular necrosis, ATN (急性腎小管壞死)", ("急性腎小管壞死", "ATN", "acute tubular necrosis", "muddy brown"), "缺血或腎毒性造成 intrinsic AKI，尿沉渣與 FENa 可輔助判讀。"),
    TopicSeed("condition", "acute-interstitial-nephritis", "Acute interstitial nephritis, AIN (急性間質性腎炎)", ("急性間質性腎炎", "AIN", "interstitial nephritis", "eosinophiluria"), "常與藥物過敏、感染或自體免疫相關，屬 intrinsic AKI。"),
    TopicSeed("condition", "chronic-kidney-disease", "Chronic kidney disease, CKD (慢性腎臟病)", ("慢性腎臟病", "CKD", "chronic kidney disease", "chronic renal insufficiency"), "腎功能或腎臟結構慢性異常，需分期、控制進展因子與併發症。"),
    TopicSeed("condition", "end-stage-kidney-disease", "End-stage kidney disease, ESKD (末期腎臟病)", ("末期腎", "ESKD", "ESRD", "end-stage renal"), "腎功能進入需 renal replacement therapy 或保守照護評估的階段。"),
    TopicSeed("condition", "uremia", "Uremia (尿毒症)", ("尿毒症", "Uremia", "uremic", "BUN"), "腎衰竭造成尿毒素累積，可引發神經、心包膜、腸胃與血液異常。"),
    TopicSeed("condition", "nephritic-syndrome", "Nephritic syndrome (腎炎症候群)", ("腎炎症候群", "Nephritic syndrome", "RBC cast", "dysmorphic RBC"), "以血尿、RBC cast、高血壓、水腫與腎功能下降為核心的腎絲球發炎表現。"),
    TopicSeed("condition", "nephrotic-syndrome", "Nephrotic syndrome (腎病症候群)", ("腎病症候群", "Nephrotic syndrome", "蛋白尿 > 3.5", "hypoalbuminemia"), "大量蛋白尿造成低白蛋白、水腫、高血脂與高凝固狀態。"),
    TopicSeed("condition", "glomerulonephritis", "Glomerulonephritis, GN (腎絲球腎炎)", ("腎絲球腎炎", "Glomerulonephritis", "GN", "glomerular disease"), "腎絲球發炎疾病群，臨床可表現為 nephritic syndrome、RPGN 或慢性腎炎。"),
    TopicSeed("condition", "rapidly-progressive-glomerulonephritis", "Rapidly progressive glomerulonephritis, RPGN (急速進行性腎絲球腎炎)", ("RPGN", "Rapid progressive", "急速進行性", "crescent"), "數週內腎功能快速惡化，病理常見 crescent formation。"),
    TopicSeed("condition", "anca-associated-vasculitis", "ANCA-associated vasculitis (ANCA 相關血管炎)", ("ANCA vasculitis", "ANCA", "c-ANCA", "p-ANCA", "Wegener", "Microscopic polyangiitis", "Churg"), "pauci-immune RPGN 重要病因，可合併肺部侵犯。"),
    TopicSeed("condition", "anti-gbm-disease", "Anti-GBM disease / Goodpasture syndrome (抗腎絲球基底膜疾病)", ("Anti-GBM", "Goodpasture", "抗基底膜", "pulmonary hemorrhage"), "anti-GBM antibody 造成腎絲球腎炎，Goodpasture syndrome 合併肺出血。"),
    TopicSeed("condition", "post-streptococcal-glomerulonephritis", "Post-streptococcal glomerulonephritis, PSGN (鏈球菌感染後腎絲球腎炎)", ("PSGN", "APSGN", "post-streptococcal", "poststreptococcal", "鏈球菌感染後", "急性鏈球菌感染後腎絲球腎炎", "ASLO", "low C3"), "A 群鏈球菌感染後免疫複合物腎炎，常見血尿、水腫、高血壓與 C3 暫時下降。"),
    TopicSeed("condition", "iga-nephropathy", "IgA nephropathy (IgA 腎病變)", ("IgA nephropathy", "Berger", "IgA 腎", "上呼吸道症狀 1~3 天"), "成人常見原發性腎絲球病變，常在上呼吸道感染後短期內肉眼血尿。"),
    TopicSeed("condition", "lupus-nephritis", "Lupus nephritis (狼瘡腎炎)", ("狼瘡腎炎", "Lupus nephritis", "anti-dsDNA", "SLE 腎"), "SLE 腎臟侵犯，可依病理分型決定治療強度。"),
    TopicSeed("condition", "minimal-change-disease", "Minimal change disease, MCD (微小變化疾病)", ("Minimal change", "MCD", "微小變化"), "足細胞病變造成 nephrotic syndrome，兒童常見且類固醇反應佳。"),
    TopicSeed("condition", "focal-segmental-glomerulosclerosis", "Focal segmental glomerulosclerosis, FSGS (局部節段性腎絲球硬化)", ("FSGS", "focal segmental", "局部節段"), "成人 nephrotic syndrome 重要原因，可為原發或次發。"),
    TopicSeed("condition", "membranous-nephropathy", "Membranous nephropathy (膜性腎病變)", ("Membranous nephropathy", "膜性腎", "spike and dome"), "成人 nephrotic syndrome 重要原因，需評估原發與繼發病因。"),
    TopicSeed("condition", "membranoproliferative-glomerulonephritis", "Membranoproliferative glomerulonephritis, MPGN (膜增生性腎絲球腎炎)", ("MPGN", "membranoproliferative", "膜增生"), "免疫複合物或補體異常相關腎絲球病變，可有低補體。"),
    TopicSeed("condition", "polycystic-kidney-disease", "Polycystic kidney disease (多囊性腎病)", ("多囊性腎", "polycystic kidney", "ADPKD", "PKD"), "遺傳性腎囊腫疾病，可造成高血壓、血尿、腎功能下降與腎外表現。"),
    TopicSeed("condition", "nephrolithiasis", "Nephrolithiasis (腎結石)", ("腎結石", "Nephrolithiasis", "kidney stone", "urinary stone"), "尿路結石可造成腎絞痛、血尿、感染或阻塞性腎損傷。"),
    TopicSeed("condition", "renal-osteodystrophy", "Renal osteodystrophy (腎性骨病變)", ("腎性骨病變", "renal osteodystrophy", "secondary hyperparathyroidism", "CKD-MBD"), "CKD 鈣磷、PTH 與 vitamin D 異常造成骨代謝疾病。"),
    # Renal diagnostics, procedures, anatomy, physiology.
    TopicSeed("diagnostic", "anion-gap", "Anion gap (陰離子間隙)", ("陰離子間隙", "Anion gap", "AG =", "delta AG", "ΔAG"), "用 Na、Cl、HCO3 估計未測量陰離子，輔助代謝性酸中毒鑑別。"),
    TopicSeed("diagnostic", "osmolal-gap", "Osmolal gap (滲透壓間隙)", ("Osmolal gap", "滲透壓間隙", "Measured osmoles", "Calculated osmoles"), "實測與計算血漿滲透壓差，可輔助 toxic alcohol 等鑑別。"),
    TopicSeed("diagnostic", "urine-anion-gap", "Urine anion gap (尿液陰離子間隙)", ("Urine anion gap", "UAG", "尿液陰離子", "UNa", "UK", "UCl"), "用尿 Na、K、Cl 推估尿 NH4 排泄，協助正常陰離子間隙代謝性酸中毒鑑別。"),
    TopicSeed("diagnostic", "urinalysis", "Urinalysis (尿液檢查)", ("尿液分析", "尿液檢查", "urinalysis", "urine sediment", "尿沉渣"), "蛋白、血尿、白血球、cast 與比重是腎臟與泌尿感染評估基礎。"),
    TopicSeed("diagnostic", "fractional-excretion-of-sodium", "Fractional excretion of sodium, FENa (鈉分率排泄)", ("FENa", "fractional excretion", "鈉分率"), "用尿鈉與肌酸酐估計腎小管鈉處理，輔助 AKI 分型。"),
    TopicSeed("diagnostic", "kidney-biopsy", "Kidney biopsy (腎臟切片)", ("腎臟切片", "kidney biopsy", "renal biopsy", "免疫螢光"), "診斷腎絲球、間質與部分腎實質疾病的重要檢查。"),
    TopicSeed("diagnostic", "cerebrospinal-fluid-analysis", "Cerebrospinal fluid analysis, CSF (腦脊髓液檢查)", ("腦脊髓液", "CSF", "lumbar puncture", "opening pressure"), "用壓力、細胞、蛋白、葡萄糖與染色培養區分 CNS infection 類型。"),
    TopicSeed("procedure", "hemodialysis", "Hemodialysis (血液透析)", ("血液透析", "hemodialysis", "HD", "洗腎"), "以體外循環移除溶質與水分，是 ESKD 與部分急症的 renal replacement therapy。"),
    TopicSeed("procedure", "peritoneal-dialysis", "Peritoneal dialysis (腹膜透析)", ("腹膜透析", "peritoneal dialysis", "PD", "CAPD"), "利用腹膜作為半透膜進行透析，可作為 ESKD 腎臟替代療法。"),
    TopicSeed("procedure", "dialysis-indications", "Dialysis indications (透析適應症)", ("透析適應症", "AEIOU", "urgent dialysis", "emergent hemodialysis"), "急性透析常依 acidosis、electrolyte、intoxication、overload、uremia 等評估。"),
    TopicSeed("procedure", "kidney-transplantation", "Kidney transplantation (腎臟移植)", ("腎臟移植", "kidney transplantation", "renal transplant"), "ESKD 的腎臟替代療法之一，需評估免疫配對、排斥與感染風險。"),
    TopicSeed("condition", "kidney-transplant-rejection", "Kidney transplant rejection (腎臟移植排斥)", ("移植排斥", "transplant rejection", "acute rejection", "chronic rejection"), "移植腎可能發生超急性、急性或慢性排斥，需依時間與病理判斷。"),
    TopicSeed("anatomy", "kidney", "Kidney (腎臟)", ("腎臟", "kidney", "renal", "nephron"), "腎臟維持體液、電解質、酸鹼、血壓、紅血球生成與代謝廢物排除。"),
    TopicSeed("anatomy", "glomerulus", "Glomerulus (腎絲球)", ("腎絲球", "glomerulus", "GBM", "podocyte"), "腎絲球濾過屏障是 proteinuria、hematuria 與 GN 的核心結構。"),
    TopicSeed("anatomy", "renal-tubule", "Renal tubule (腎小管)", ("腎小管", "renal tubule", "proximal tubule", "distal tubule", "collecting duct"), "腎小管調控水、電解質、酸鹼與藥物/毒物處理。"),
    TopicSeed("physiology", "renal-sodium-water-handling", "Renal sodium and water handling (腎臟鈉水處理)", ("鈉水", "ADH", "AVP", "aldosterone", "urine osmolality"), "腎臟透過 ADH、aldosterone、GFR 與 tubule transport 維持鈉水平衡。"),
    TopicSeed("physiology", "renal-potassium-handling", "Renal potassium handling (腎臟鉀離子處理)", ("鉀離子平衡", "potassium handling", "aldosterone", "高血鉀", "低血鉀"), "遠端腎小管與 aldosterone 決定鉀排泄，是高/低血鉀鑑別核心。"),
    TopicSeed("physiology", "renal-acid-base-handling", "Renal acid-base handling (腎臟酸鹼處理)", ("腎臟酸鹼", "ammonium", "NH4", "bicarbonate reabsorption", "HCO3 reabsorption"), "腎臟藉由 HCO3 再吸收、H+ 分泌與 NH4 排泄維持酸鹼平衡。"),
    # Infectious disease syndromes and organisms.
    TopicSeed("condition", "bacterial-meningitis", "Bacterial meningitis (細菌性腦膜炎)", ("細菌性腦膜炎", "Bacterial meningitis", "purulent meningitis", "Kernig", "Brudzinski"), "急性 CNS infection，常有發燒、頭痛、頸部僵硬與 CSF neutrophilic pleocytosis。"),
    TopicSeed("condition", "viral-meningitis", "Viral meningitis (病毒性腦膜炎)", ("病毒性腦膜炎", "aseptic meningitis", "Enterovirus", "HSV2"), "CSF 通常淋巴球為主、葡萄糖較正常，常由 enterovirus 或 HSV 等造成。"),
    TopicSeed("condition", "encephalitis", "Encephalitis (腦炎)", ("腦炎", "Encephalitis", "HSV encephalitis", "意識改變"), "腦實質發炎，常有意識改變、癲癇或局部神經學症狀。"),
    TopicSeed("condition", "urinary-tract-infection", "Urinary tract infection, UTI (泌尿道感染)", ("泌尿道感染", "UTI", "urinary tract infection", "膀胱炎", "腎盂腎炎"), "泌尿道細菌感染，依位置與複雜度區分 cystitis、pyelonephritis 與 complicated UTI。"),
    TopicSeed("condition", "cystitis", "Cystitis (膀胱炎)", ("膀胱炎", "Cystitis", "dysuria", "frequency"), "下泌尿道感染，常有頻尿、急尿、解尿疼痛。"),
    TopicSeed("condition", "pyelonephritis", "Pyelonephritis (腎盂腎炎)", ("腎盂腎炎", "Pyelonephritis", "flank pain", "CVA tenderness"), "上泌尿道感染，可有發燒、腰痛與菌血症風險。"),
    TopicSeed("condition", "cellulitis", "Cellulitis (蜂窩性組織炎)", ("蜂窩性組織炎", "Cellulitis", "soft tissue infection"), "皮膚與軟組織感染，常由 streptococci 或 Staphylococcus aureus 造成。"),
    TopicSeed("condition", "necrotizing-fasciitis", "Necrotizing fasciitis (壞死性筋膜炎)", ("壞死性筋膜炎", "Necrotizing fasciitis", "flesh eating", "toxin"), "快速進展的深部軟組織感染，需早期手術評估與廣效抗生素。"),
    TopicSeed("condition", "impetigo", "Impetigo (膿痂疹)", ("膿痂疹", "Impetigo", "honey-colored crust", "bullous impetigo"), "表皮層細菌感染，常由 GAS 或 S. aureus 造成，可為非水泡型或水泡型。"),
    TopicSeed("condition", "septic-arthritis", "Septic arthritis (感染性關節炎)", ("感染性關節炎", "Septic arthritis", "infectious arthritis"), "關節腔感染造成急性單關節痛與發炎，需快速抽液與治療。"),
    TopicSeed("condition", "infectious-gastroenteritis", "Infectious gastroenteritis (感染性腸胃炎)", ("感染性腸胃炎", "gastroenteritis", "腸胃道感染", "diarrhea"), "由病毒、細菌、毒素或寄生蟲造成腹瀉、嘔吐或腹痛。"),
    TopicSeed("condition", "clostridioides-difficile-infection", "Clostridioides difficile infection (困難梭菌感染)", ("Clostridium difficile", "Clostridioides difficile", "C. difficile", "偽膜性腸炎", "pseudomembranous"), "抗生素後腸道菌相改變造成 toxin-mediated colitis。"),
    TopicSeed("condition", "cholera", "Cholera (霍亂)", ("霍亂", "Cholera", "Vibrio cholerae", "rice-water stool"), "Vibrio cholerae 毒素造成大量水瀉與脫水。"),
    TopicSeed("condition", "salmonellosis", "Salmonellosis (沙門氏菌感染)", ("Salmonella", "沙門氏菌", "typhoid", "enteric fever"), "Salmonella 可造成腸胃炎、菌血症或傷寒樣疾病。"),
    TopicSeed("condition", "shigellosis", "Shigellosis (志賀氏菌感染)", ("Shigella", "志賀氏菌", "bacillary dysentery"), "Shigella 造成發炎性腹瀉與痢疾，具低感染劑量。"),
    TopicSeed("condition", "campylobacter-infection", "Campylobacter infection (空腸彎曲桿菌感染)", ("Campylobacter", "空腸彎曲桿菌", "C. jejuni"), "常見細菌性腸炎原因，可與 Guillain-Barre syndrome 相關。"),
    TopicSeed("condition", "escherichia-coli-infection", "Escherichia coli infection (大腸桿菌感染)", ("Escherichia coli", "E. coli", "大腸桿菌", "EHEC", "ETEC"), "E. coli 可造成 UTI、腸胃炎、菌血症與多種院內感染。"),
    TopicSeed("condition", "hemolytic-uremic-syndrome", "Hemolytic uremic syndrome, HUS (溶血性尿毒症候群)", ("HUS", "hemolytic uremic", "溶血性尿毒", "EHEC"), "常與 Shiga toxin 相關，造成溶血、血小板低下與 AKI。"),
    TopicSeed("condition", "staphylococcus-aureus-infection", "Staphylococcus aureus infection (金黃色葡萄球菌感染)", ("Staphylococcus aureus", "S. aureus", "金黃色葡萄球菌", "MSSA", "MRSA"), "可造成皮膚軟組織感染、菌血症、心內膜炎、肺炎、食物中毒與 toxin syndromes。"),
    TopicSeed("condition", "methicillin-resistant-staphylococcus-aureus", "MRSA infection (抗甲氧西林金黃色葡萄球菌感染)", ("MRSA", "Methicillin resistant", "抗甲氧西林"), "PBP 改變造成 beta-lactam 抗藥的 S. aureus，嚴重感染常需抗 MRSA 藥物。"),
    TopicSeed("condition", "streptococcus-pyogenes-infection", "Streptococcus pyogenes infection (A 群鏈球菌感染)", ("Streptococcus pyogenes", "Group A streptococcus", "GAS", "化膿性鏈球菌"), "GAS 可造成咽炎、皮膚感染、猩紅熱、毒性休克、風濕熱與 PSGN。"),
    TopicSeed("condition", "streptococcus-pneumoniae-infection", "Streptococcus pneumoniae infection (肺炎鏈球菌感染)", ("Streptococcus pneumoniae", "S. pneumoniae", "肺炎雙球菌", "Pneumococcus"), "可造成肺炎、腦膜炎、中耳炎與菌血症，莢膜是重要毒力因子。"),
    TopicSeed("condition", "enterococcus-infection", "Enterococcus infection (腸球菌感染)", ("Enterococcus", "E. faecalis", "腸球菌", "VRE"), "常見膽道、泌尿道、院內與心內膜感染病原，抗藥性治療需特別注意。"),
    TopicSeed("condition", "neisseria-meningitidis-infection", "Neisseria meningitidis infection (腦膜炎雙球菌感染)", ("Neisseria meningitidis", "腦膜炎雙球菌", "meningococcus", "petechiae", "purpuric rash"), "可造成流行性腦膜炎與敗血症，密切接觸者需預防性投藥與通報。"),
    TopicSeed("condition", "gonorrhea", "Gonorrhea (淋病)", ("Gonorrhea", "Neisseria gonorrhoeae", "淋病", "淋菌"), "性傳染病，可造成尿道炎、子宮頸炎、PID、附睪炎或播散性感染。"),
    TopicSeed("condition", "listeriosis", "Listeriosis (李斯特菌感染)", ("Listeria", "李斯特", "Listeriosis", "monocytogenes"), "老人、孕婦、免疫不全者可有菌血症或腦膜炎，常以 ampicillin 為核心治療。"),
    TopicSeed("condition", "diphtheria", "Diphtheria (白喉)", ("Diphtheria", "白喉", "Corynebacterium diphtheriae", "pseudomembrane"), "白喉毒素可造成咽部偽膜、心肌炎與神經病變。"),
    TopicSeed("condition", "anthrax", "Anthrax (炭疽病)", ("Anthrax", "Bacillus anthracis", "炭疽", "black eschar"), "人畜共通感染，可為皮膚、吸入或腸胃型。"),
    TopicSeed("condition", "botulism", "Botulism (肉毒桿菌中毒)", ("Botulism", "Clostridium botulinum", "肉毒", "flaccid paralysis"), "肉毒毒素抑制 acetylcholine 釋放，造成下行性無力與自主神經症狀。"),
    TopicSeed("condition", "tetanus", "Tetanus (破傷風)", ("Tetanus", "Clostridium tetani", "破傷風", "lockjaw"), "破傷風毒素阻斷抑制性神經傳導，造成肌肉痙攣。"),
    TopicSeed("condition", "gas-gangrene", "Gas gangrene (氣性壞疽)", ("Gas gangrene", "Clostridium perfringens", "氣性壞疽", "產氣芽孢"), "Clostridium perfringens 傷口感染可造成肌肉壞死、產氣與毒血症。"),
    TopicSeed("condition", "nocardiosis", "Nocardiosis (奴卡氏菌感染)", ("Nocardia", "奴卡氏菌", "nocardiosis", "weak acid-fast"), "可造成肺部、皮膚或中樞感染，免疫不全者風險較高。"),
    TopicSeed("condition", "actinomycosis", "Actinomycosis (放線菌病)", ("Actinomyces", "放射線菌", "Actinomycosis", "sulfur granules"), "厭氧絲狀菌感染，常見慢性下顎臉部或腹盆腔病灶。"),
    TopicSeed("condition", "pseudomonas-aeruginosa-infection", "Pseudomonas aeruginosa infection (綠膿桿菌感染)", ("Pseudomonas", "P. aeruginosa", "綠膿桿菌"), "常見院內、燒傷、呼吸器、免疫低下感染病原，抗生素選擇需覆蓋抗藥性。"),
    TopicSeed("condition", "legionnaires-disease", "Legionnaires disease (退伍軍人病)", ("Legionella", "退伍軍人菌", "Legionnaires", "atypical pneumonia"), "Legionella pneumophila 造成 atypical pneumonia，常與水源暴露相關。"),
    TopicSeed("condition", "pertussis", "Pertussis (百日咳)", ("Pertussis", "Bordetella", "百日咳", "whooping cough"), "Bordetella pertussis 造成陣發性咳嗽，疫苗與暴露後預防重要。"),
    TopicSeed("condition", "vibrio-vulnificus-infection", "Vibrio vulnificus infection (海洋弧菌感染)", ("Vibrio vulnificus", "海洋弧菌", "V. vulnificus"), "海鮮或海水暴露後可造成敗血症或壞死性軟組織感染，肝病者風險高。"),
    TopicSeed("condition", "syphilis", "Syphilis (梅毒)", ("Syphilis", "Treponema pallidum", "梅毒", "RPR", "VDRL"), "Treponema pallidum 性傳染病，分期影響表現與治療策略。"),
    TopicSeed("condition", "lyme-disease", "Lyme disease (萊姆病)", ("Lyme", "Borrelia burgdorferi", "萊姆病", "erythema migrans"), "蜱媒 Borrelia 感染，可有游走性紅斑、神經、心臟與關節表現。"),
    TopicSeed("condition", "leptospirosis", "Leptospirosis (鉤端螺旋體病)", ("Leptospira", "鉤端螺旋體", "Leptospirosis", "Weil"), "動物尿液或水土暴露相關 spirochete infection，可侵犯肝腎。"),
    TopicSeed("condition", "rickettsial-disease", "Rickettsial disease (立克次體疾病)", ("Rickettsia", "立克次體", "scrub typhus", "恙蟲病", "Q fever"), "節肢動物媒介或人畜共通感染，常以發燒、皮疹或 eschar 呈現。"),
    TopicSeed("condition", "chlamydia-infection", "Chlamydia infection (披衣菌感染)", ("Chlamydia", "披衣菌", "C. trachomatis"), "絕對細胞內病原，可造成泌尿生殖道、眼部與肺部感染。"),
    TopicSeed("condition", "hiv-infection", "HIV infection (人類免疫不全病毒感染)", ("HIV", "Human immunodeficiency", "人類免疫不全病毒", "CD4", "viral load"), "HIV 感染 CD4 T cell，慢性免疫破壞可進展至 AIDS。"),
    TopicSeed("condition", "aids", "AIDS (後天免疫缺乏症候群)", ("AIDS", "後天免疫", "CD4 < 200", "AIDS-defining"), "HIV 感染進展至 CD4 < 200 或出現 AIDS-defining condition。"),
    TopicSeed("condition", "pneumocystis-jirovecii-pneumonia", "Pneumocystis jirovecii pneumonia, PJP (肺囊蟲肺炎)", ("Pneumocystis", "PJP", "PCP", "肺囊蟲"), "AIDS 常見伺機感染，造成間質性肺炎與低氧。"),
    TopicSeed("condition", "toxoplasmosis", "Toxoplasmosis (弓漿蟲感染)", ("Toxoplasma", "弓漿蟲", "toxoplasmosis", "eccentric target"), "免疫低下者可造成多發性中樞神經病灶。"),
    TopicSeed("condition", "cytomegalovirus-infection", "Cytomegalovirus infection, CMV (巨細胞病毒感染)", ("CMV", "Cytomegalovirus", "巨細胞病毒", "retinitis"), "免疫低下者可造成 retinitis、colitis、encephalitis 等。"),
    TopicSeed("condition", "cryptococcosis", "Cryptococcosis (隱球菌感染)", ("Cryptococcus", "隱球菌", "cryptococcal", "India ink"), "免疫低下者可造成肺部感染與 cryptococcal meningitis。"),
    TopicSeed("condition", "candidiasis", "Candidiasis (念珠菌感染)", ("Candida", "Candidiasis", "念珠菌", "thrush", "esophageal candidiasis"), "黏膜、食道或侵襲性感染，免疫低下與抗生素暴露增加風險。"),
    TopicSeed("condition", "kaposi-sarcoma", "Kaposi sarcoma (卡波西肉瘤)", ("Kaposi", "HHV8", "卡波西"), "HHV-8 相關腫瘤，HIV/AIDS 免疫低下者較常見。"),
    # Antimicrobials, antiviral, antifungal, infection-control frameworks.
    TopicSeed("drug", "penicillins", "Penicillins (青黴素類)", ("Penicillin", "PCN", "青黴素", "Ampicillin", "Amoxicillin", "Piperacillin"), "beta-lactam 類抗生素，抑制細胞壁 transpeptidase/PBP。"),
    TopicSeed("drug", "beta-lactamase-inhibitors", "Beta-lactamase inhibitors (β-lactamase 抑制劑)", ("clavulanate", "sulbactam", "tazobactam", "β lactamase inhibitor", "beta-lactamase inhibitor"), "與 beta-lactam 合併以抑制 beta-lactamase，擴大對產酶菌效果。"),
    TopicSeed("drug", "cephalosporins", "Cephalosporins (頭孢子菌素類)", ("Cephalosporin", "Cefazolin", "Ceftriaxone", "Ceftazidime", "Cefepime", "頭孢"), "beta-lactam 類，依世代涵蓋不同 GPC/GNB、CNS、Pseudomonas 或 MRSA 活性。"),
    TopicSeed("drug", "carbapenems", "Carbapenems (碳青黴烯類)", ("Carbapenem", "Imipenem", "Meropenem", "Ertapenem", "碳青黴烯"), "廣效 beta-lactam，常用於 ESBL/AmpC 等抗藥性 GNB。"),
    TopicSeed("drug", "monobactams", "Monobactams (單環 β-lactam 類)", ("Monobactam", "Aztreonam", "單環"), "Aztreonam 主要抗 GNB，對 penicillin allergy 時可作替代選項之一。"),
    TopicSeed("drug", "vancomycin", "Vancomycin (萬古黴素)", ("Vancomycin", "萬古黴素", "red man", "trough"), "glycopeptide 抗 GPC 藥物，用於 MRSA、抗藥性腸球菌相關情境與嚴重 GPC 感染。"),
    TopicSeed("drug", "aminoglycosides", "Aminoglycosides (胺基糖苷類)", ("Aminoglycoside", "Gentamicin", "Amikacin", "Tobramycin", "胺基糖苷"), "30S 抑制劑，常與 beta-lactam 合併治療嚴重 GNB 或協同治療，但有腎毒性與耳毒性。"),
    TopicSeed("drug", "macrolides", "Macrolides (巨環內酯類)", ("Macrolide", "Azithromycin", "Clarithromycin", "Erythromycin", "巨環內酯"), "50S 抑制劑，涵蓋 atypical pneumonia pathogens、部分 GPC 與 MAC 預防/治療。"),
    TopicSeed("drug", "clindamycin", "Clindamycin (克林黴素)", ("Clindamycin", "克林黴素", "Lincosamide"), "50S 抑制劑，抗 GPC 與部分厭氧菌，也可抑制 toxin production。"),
    TopicSeed("drug", "linezolid", "Linezolid (利奈唑胺)", ("Linezolid", "Oxazolidinone", "利奈唑胺"), "抗多重抗藥 GPC，可用於 MRSA 或 VRE，但需注意骨髓抑制與 serotonin syndrome。"),
    TopicSeed("drug", "tetracyclines", "Tetracyclines (四環黴素類)", ("Tetracycline", "Doxycycline", "Minocycline", "四環黴素"), "30S 抑制劑，常用於 rickettsia、chlamydia、spirochete、acne 與部分寄生蟲預防。"),
    TopicSeed("drug", "fluoroquinolones", "Fluoroquinolones (氟喹諾酮類)", ("Fluoroquinolone", "Ciprofloxacin", "Levofloxacin", "Moxifloxacin", "氟喹諾酮"), "抑制 DNA gyrase/topoisomerase，涵蓋多種 GNB、呼吸道或泌尿感染病原。"),
    TopicSeed("drug", "trimethoprim-sulfamethoxazole", "Trimethoprim-sulfamethoxazole, TMP-SMX (複方新諾明)", ("TMP/SMX", "TMP-SMX", "Trimethoprim", "Sulfamethoxazole", "Baktar"), "葉酸代謝抑制組合，用於 PJP、UTI、Nocardia、部分 MRSA 等。"),
    TopicSeed("drug", "metronidazole", "Metronidazole (甲硝唑)", ("Metronidazole", "甲硝唑", "Flagyl"), "抗厭氧菌與部分原蟲藥物，常用於腹腔、骨盆、C. difficile 或原蟲感染情境。"),
    TopicSeed("drug", "antifungal-agents", "Antifungal agents (抗黴菌藥物)", ("Antifungal", "抗黴菌", "Amphotericin", "Azole", "Echinocandin", "Fluconazole"), "抗黴菌藥物包含 polyene、azole、echinocandin 等類別，選擇依病原與侵犯部位。"),
    TopicSeed("drug", "acyclovir", "Acyclovir (阿昔洛韋)", ("Acyclovir", "Valacyclovir", "阿昔洛韋", "HSV", "VZV"), "抗 herpesvirus 核苷類藥物，用於 HSV/VZV 感染。"),
    TopicSeed("drug", "ganciclovir", "Ganciclovir / Valganciclovir (更昔洛韋類)", ("Ganciclovir", "Valganciclovir", "更昔洛韋", "CMV"), "抗 CMV 藥物，可造成骨髓抑制，免疫低下 CMV disease 常用。"),
    TopicSeed("drug", "antiretroviral-therapy", "Antiretroviral therapy, ART (抗反轉錄病毒治療)", ("HAART", "ART", "antiretroviral", "NRTI", "NNRTI", "Protease inhibitor", "Integrase inhibitor"), "HIV 治療以多藥組合壓制病毒量、恢復 CD4 並降低 AIDS 風險。"),
    TopicSeed("drug", "hiv-prep-pep", "HIV PrEP and PEP (HIV 暴露前與暴露後預防)", ("PrEP", "PEP", "post-exposure", "preexposure", "TDF/FTC"), "高風險暴露前或暴露後抗病毒預防策略，時間與藥物組合需依現行 guideline 複核。"),
    TopicSeed("diagnostic", "hiv-testing", "HIV testing (HIV 檢測)", ("HIV testing", "ELISA", "Western blot", "p24", "HIV viral load", "HIV RNA"), "HIV 診斷與追蹤包含抗原抗體篩檢、確認試驗、病毒量與 CD4 count。"),
    TopicSeed("guideline", "aids-defining-conditions", "AIDS-defining conditions (AIDS 定義疾病)", ("AIDS-defining", "AIDS surveillance", "CD4 < 200", "伺機性感染"), "AIDS 依 CD4 < 200 或特定 opportunistic infection/腫瘤定義，部分地區對 TB 定義不同。"),
    TopicSeed("guideline", "opportunistic-infection-prophylaxis", "Opportunistic infection prophylaxis (伺機性感染預防)", ("opportunistic infection prophylaxis", "PJP prophylaxis", "MAC prophylaxis", "CD4 < 200", "CD4 < 50"), "HIV/AIDS 依 CD4 閾值給予 PJP、Toxoplasma、MAC 等預防。"),
    TopicSeed("guideline", "meningococcal-exposure-prophylaxis", "Meningococcal exposure prophylaxis (腦膜炎雙球菌暴露後預防)", ("rifampin", "腦膜炎雙球菌", "接觸者", "prophylaxis", "呼吸道隔離"), "Neisseria meningitidis 感染需通報、初期呼吸道隔離與密切接觸者預防性投藥。"),
    TopicSeed("guideline", "notifiable-infectious-diseases", "Notifiable infectious diseases (法定傳染病通報)", ("法定傳染病", "通報", "notifiable", "CDC Taiwan", "衛生單位"), "特定傳染病依法需在規定時限內通報，實際分類與時限需查最新官方規定。"),
    TopicSeed("concept", "gram-stain-classification", "Gram stain classification (革蘭氏染色分類)", ("Gram positive", "Gram negative", "革蘭氏", "GPC", "GNB", "GPB"), "以 Gram stain、形態、觸媒、凝固酶、溶血等特徵建立細菌鑑別框架。"),
    TopicSeed("concept", "antibiotic-resistance", "Antibiotic resistance (抗生素抗藥性)", ("抗藥性", "antibiotic resistance", "ESBL", "AmpC", "VRE", "PRSP"), "抗藥性可由 beta-lactamase、PBP 改變、efflux pump 等機制造成，影響經驗性與確定治療。"),
    TopicSeed("concept", "beta-lactam-mechanism", "Beta-lactam mechanism (β-lactam 作用機轉)", ("beta-lactam ring", "β-lactam", "PBP", "transpeptidase", "細胞壁"), "beta-lactam 藉抑制 PBP/transpeptidase 阻斷 peptidoglycan cross-linking。"),
    TopicSeed("concept", "opportunistic-infection", "Opportunistic infection (伺機性感染)", ("伺機性感染", "opportunistic infection", "CD4", "免疫不全"), "免疫功能下降時由平時低致病性或潛伏病原造成的感染。"),
)


FOURTH_BOOK_SEEDS: tuple[TopicSeed, ...] = (
    # Rheumatology and immunology.
    TopicSeed("condition", "systemic-lupus-erythematosus", "Systemic lupus erythematosus, SLE (全身性紅斑狼瘡)", ("Systemic lupus erythematosus", "SLE", "紅斑性狼瘡", "全身性紅斑狼瘡", "malar rash", "Anti-ds DNA", "Anti-Sm"), "多系統自體免疫疾病，常侵犯皮膚、關節、腎臟、血液與中樞神經。"),
    TopicSeed("condition", "cutaneous-lupus-erythematosus", "Cutaneous lupus erythematosus (皮膚型紅斑狼瘡)", ("cutaneous lupus", "Discoid lupus", "ACLE", "SCLE", "DLE", "Malar rash", "photosensitivity"), "SLE 或局限性 lupus 的皮膚表現，包含 acute、subacute 與 discoid 型態。"),
    TopicSeed("condition", "antiphospholipid-syndrome", "Antiphospholipid syndrome, APS (抗磷脂質抗體症候群)", ("antiphospholipid", "APS", "抗磷脂", "lupus anticoagulant", "anticardiolipin", "β2-glycoprotein"), "以動靜脈血栓或妊娠 morbidity 合併 antiphospholipid antibodies 為核心。"),
    TopicSeed("condition", "rheumatoid-arthritis", "Rheumatoid arthritis, RA (類風濕性關節炎)", ("Rheumatoid arthritis", "RA", "類風濕", "Anti-CCP", "rheumatoid factor", "morning stiffness"), "慢性對稱性發炎性多關節炎，滑膜炎可造成 bone erosion 與關節變形。"),
    TopicSeed("condition", "felty-syndrome", "Felty syndrome (Felty 氏症候群)", ("Felty", "neutropenia", "splenomegaly", "RA"), "RA 合併 neutropenia 與 splenomegaly，感染風險增加。"),
    TopicSeed("condition", "atlantoaxial-subluxation", "Atlantoaxial subluxation (寰樞椎半脫位)", ("Atlantoaxial", "寰椎", "樞椎", "C1", "C2", "dens"), "RA 頸椎侵犯可造成 C1-C2 instability 與神經壓迫風險。"),
    TopicSeed("condition", "sjogren-syndrome", "Sjogren syndrome (修格蘭氏症候群)", ("Sjogren", "Sjögren", "修格蘭", "乾燥症", "anti-SSA", "anti-SSB", "sicca"), "外分泌腺自體免疫疾病，造成乾眼、乾口並可合併系統性表現。"),
    TopicSeed("condition", "systemic-sclerosis", "Systemic sclerosis (全身性硬化症)", ("Systemic sclerosis", "Scleroderma", "硬皮症", "CREST", "anti-centromere", "anti-Scl-70"), "纖維化與血管病變造成皮膚硬化、Raynaud、肺高壓、腎危象等。"),
    TopicSeed("condition", "scleroderma-renal-crisis", "Scleroderma renal crisis (硬皮症腎危象)", ("scleroderma renal crisis", "硬皮症腎", "malignant hypertension", "Scleroderma renal"), "systemic sclerosis 急性高血壓與腎衰竭表現，需快速辨識。"),
    TopicSeed("condition", "polymyositis-dermatomyositis", "Polymyositis and dermatomyositis (多發性肌炎與皮肌炎)", ("Polymyositis", "Dermatomyositis", "多發性肌炎", "皮肌炎", "Gottron", "heliotrope", "CK"), "自體免疫發炎性肌病，造成近端肌無力；dermatomyositis 具典型皮疹與癌症關聯。"),
    TopicSeed("condition", "mixed-connective-tissue-disease", "Mixed connective tissue disease, MCTD (混合性結締組織病)", ("Mixed connective tissue", "MCTD", "Anti-RNP", "混合性結締"), "重疊 SLE、systemic sclerosis、myositis 等表現並與 anti-RNP 相關。"),
    TopicSeed("condition", "relapsing-polychondritis", "Relapsing polychondritis (復發性多軟骨炎)", ("Relapsing polychondritis", "多軟骨炎", "auricular chondritis"), "反覆軟骨發炎，可侵犯耳、鼻、氣管與關節。"),
    TopicSeed("condition", "large-vessel-vasculitis", "Large-vessel vasculitis (大血管炎)", ("large vessel vasculitis", "大血管炎", "Takayasu", "Giant cell arteritis", "temporal arteritis"), "主要侵犯主動脈及其分支的血管炎類群。"),
    TopicSeed("condition", "giant-cell-arteritis", "Giant cell arteritis / temporal arteritis, GCA (巨細胞動脈炎／顳動脈炎)", ("Giant cell arteritis", "GCA", "temporal arteritis", "Temporal arteritis", "顳動脈血管炎", "巨細胞動脈炎", "jaw claudication"), "老年人新發頭痛、顳動脈與大血管炎，需注意視力喪失、下顎跛行與 polymyalgia rheumatica 關聯。"),
    TopicSeed("condition", "polymyalgia-rheumatica", "Polymyalgia rheumatica, PMR (風濕性多肌痛)", ("Polymyalgia rheumatica", "PMR", "風濕性多肌痛", "肩帶", "骨盆帶"), "老年人肩帶與骨盆帶疼痛僵硬，可與 GCA 相關。"),
    TopicSeed("condition", "takayasu-arteritis", "Takayasu arteritis (高安氏動脈炎)", ("Takayasu", "高安氏", "pulseless disease", "subclavian"), "年輕女性大血管炎，可造成脈搏差異、血壓差與分支血管狹窄。"),
    TopicSeed("condition", "polyarteritis-nodosa", "Polyarteritis nodosa, PAN (結節性多動脈炎)", ("Polyarteritis nodosa", "PAN", "結節性多動脈炎", "HBV", "microaneurysm"), "中型血管壞死性血管炎，可與 HBV 相關，通常不侵犯肺微血管。"),
    TopicSeed("condition", "kawasaki-disease", "Kawasaki disease (川崎病)", ("Kawasaki", "川崎病", "mucocutaneous lymph node", "coronary aneurysm"), "兒童中型血管炎，需注意冠狀動脈瘤風險。"),
    TopicSeed("condition", "iga-vasculitis", "IgA vasculitis / Henoch-Schonlein purpura (IgA 血管炎)", ("Henoch", "Schonlein", "HSP", "IgA vasculitis", "紫斑", "腹痛"), "IgA 免疫複合物血管炎，常見 palpable purpura、腹痛、關節痛與腎炎。"),
    TopicSeed("condition", "behcet-disease", "Behcet disease (貝賽特氏症)", ("Behcet", "貝賽特", "oral ulcer", "genital ulcer", "pathergy"), "復發性口腔/生殖器潰瘍、眼炎與血管炎相關疾病。"),
    TopicSeed("condition", "ankylosing-spondylitis", "Ankylosing spondylitis, AS (僵直性脊椎炎)", ("Ankylosing spondylitis", "僵直性脊椎炎", "HLA-B27", "sacroiliitis", "bamboo spine"), "seronegative spondyloarthritis，造成發炎性下背痛與薦髂關節炎。"),
    TopicSeed("condition", "psoriatic-arthritis", "Psoriatic arthritis (乾癬性關節炎)", ("Psoriatic arthritis", "乾癬性關節炎", "pencil-in-cup", "dactylitis"), "乾癬相關發炎性關節炎，可有指趾炎、附著點炎與脊椎侵犯。"),
    TopicSeed("condition", "reactive-arthritis", "Reactive arthritis (反應性關節炎)", ("Reactive arthritis", "反應性關節炎", "Reiter", "urethritis", "conjunctivitis"), "感染後無菌性關節炎，常與泌尿生殖道或腸胃感染相關。"),
    TopicSeed("condition", "enteropathic-arthritis", "Enteropathic arthritis (腸病性關節炎)", ("Enteropathic arthritis", "IBD arthritis", "腸病性關節炎", "Crohn", "ulcerative colitis"), "IBD 相關周邊或中軸關節炎。"),
    TopicSeed("condition", "osteoarthritis", "Osteoarthritis, OA (退化性關節炎)", ("Osteoarthritis", "OA", "退化性關節炎", "Heberden", "Bouchard"), "軟骨退化與骨贅形成造成機械性關節痛，常侵犯 DIP、PIP、膝、髖等。"),
    TopicSeed("condition", "calcium-pyrophosphate-deposition-disease", "Calcium pyrophosphate deposition disease, CPPD (焦磷酸鈣沉積病)", ("CPPD", "pseudogout", "假性痛風", "chondrocalcinosis", "焦磷酸鈣"), "CPP crystal 關節病，可表現為 pseudogout 與 chondrocalcinosis。"),
    TopicSeed("condition", "anaphylaxis", "Anaphylaxis (全身性過敏反應)", ("Anaphylaxis", "過敏性休克", "全身性過敏", "epinephrine"), "IgE 或非 IgE 途徑造成快速全身性過敏反應，可危及呼吸與循環。"),
    TopicSeed("condition", "urticaria-angioedema", "Urticaria and angioedema (蕁麻疹與血管性水腫)", ("Urticaria", "Angioedema", "蕁麻疹", "血管性水腫"), "皮膚肥大細胞介導反應，表現為 wheal、pruritus 或深層腫脹。"),
    TopicSeed("condition", "allergic-rhinitis", "Allergic rhinitis (過敏性鼻炎)", ("Allergic rhinitis", "過敏性鼻炎", "hay fever", "sneezing"), "IgE mediated 鼻黏膜發炎，造成鼻塞、流鼻水、打噴嚏與眼鼻癢。"),
    TopicSeed("condition", "drug-hypersensitivity", "Drug hypersensitivity (藥物過敏)", ("drug allergy", "drug hypersensitivity", "藥物過敏", "Steven", "SJS", "TEN"), "藥物引發免疫或類免疫不良反應，需分辨立即型與延遲型嚴重皮膚反應。"),
    TopicSeed("diagnostic", "antinuclear-antibody", "Antinuclear antibody, ANA (抗核抗體)", ("ANA", "antinuclear antibody", "抗核抗體"), "SLE 等自體免疫疾病常用篩檢抗體，敏感度高但特異性有限。"),
    TopicSeed("diagnostic", "anti-ccp-antibody", "Anti-CCP antibody (抗環瓜氨酸抗體)", ("Anti-CCP", "ACPA", "抗環瓜氨酸", "citrullinated"), "RA 診斷與預後評估的重要自體抗體，特異性較 RF 高。"),
    TopicSeed("diagnostic", "rheumatoid-factor", "Rheumatoid factor, RF (類風濕因子)", ("Rheumatoid factor", "RF", "類風濕因子", "Anti-IgG Fc"), "RA 常見自體抗體，亦可見於感染、其他自體免疫病與老年人。"),
    TopicSeed("guideline", "sle-classification-criteria", "SLE classification criteria (SLE 分類準則)", ("SLE criteria", "SLE 診斷準則", "11 項", "Malar rash", "ANA"), "SLE 分類準則整合皮膚、關節、漿膜、腎臟、神經、血液與免疫指標。"),
    TopicSeed("guideline", "acr-eular-ra-classification-criteria", "ACR/EULAR RA classification criteria (RA 分類準則)", ("ACR/EULAR", "RA classification", "類風濕性關節炎", "score", "synovitis"), "RA 分類以關節侵犯、serology、acute phase reactants 與症狀時間加總評分。"),
    TopicSeed("physiology", "hypersensitivity-reactions", "Hypersensitivity reactions (過敏反應分類)", ("hypersensitivity", "Type I", "Type II", "Type III", "Type IV", "過敏反應"), "Gell-Coombs hypersensitivity 分類連結 IgE、抗體、免疫複合物與 T cell-mediated 反應。"),
    TopicSeed("physiology", "complement-system", "Complement system (補體系統)", ("complement", "補體", "C3", "C4", "CH50"), "補體參與 opsonization、發炎、細胞溶解與免疫複合物清除。"),
    TopicSeed("physiology", "cytokine-signaling", "Cytokine signaling (細胞激素訊號)", ("cytokine", "TNF", "IL-1", "IL-6", "JAK", "細胞激素"), "cytokine 網路驅動發炎性關節炎、免疫治療與小分子標靶治療。"),
    TopicSeed("drug", "nsaids", "NSAIDs (非類固醇消炎藥)", ("NSAID", "非類固醇", "Celecoxib", "Cox-2", "Ibuprofen", "Indomethacin"), "抑制 cyclooxygenase 以止痛抗發炎，需注意 GI、腎臟與心血管風險。"),
    TopicSeed("drug", "hydroxychloroquine", "Hydroxychloroquine (羥氯奎)", ("Hydroxychloroquine", "Plaquenil", "羥氯奎", "奎寧"), "SLE 與 RA 常用免疫調節藥，需注意視網膜毒性監測。"),
    TopicSeed("drug", "methotrexate", "Methotrexate, MTX (甲氨蝶呤)", ("Methotrexate", "MTX", "甲氨蝶呤"), "抗葉酸藥物；低劑量為 RA 核心 DMARD，高劑量用於部分腫瘤治療。"),
    TopicSeed("drug", "conventional-dmards", "Conventional DMARDs (傳統疾病修飾抗風濕藥)", ("DMARD", "Sulfasalazine", "Leflunomide", "Hydroxychloroquine", "Methotrexate"), "RA 等發炎性關節炎的 disease-modifying therapy，作用慢但可減少結構破壞。"),
    TopicSeed("drug", "biologic-dmards", "Biologic DMARDs (生物製劑抗風濕藥)", ("Biological agents", "biologic DMARD", "Etanercept", "Adalimumab", "Rituximab", "Abatacept", "Tocilizumab"), "針對 TNF、B cell、T cell costimulation、IL-6 等的免疫標靶治療。"),
    TopicSeed("drug", "tnf-inhibitors", "TNF inhibitors (TNF 抑制劑)", ("Anti-TNF", "TNF inhibitor", "Etanercept", "Adalimumab", "Golimumab", "Certolizumab"), "抑制 TNF-alpha 發炎訊號，用於 RA、AS、IBD 等；需注意 TB/HBV reactivation。"),
    TopicSeed("drug", "jak-inhibitors", "JAK inhibitors (JAK 抑制劑)", ("JAK inhibitor", "Tofacitinib", "Baricitinib", "JAK1", "JAK2", "JAK3"), "小分子免疫調節藥，阻斷 cytokine receptor 下游 JAK/STAT 訊號。"),
    TopicSeed("drug", "immunosuppressants", "Immunosuppressants (免疫抑制劑)", ("immunosuppressant", "Azathioprine", "Mycophenolate", "Cyclosporin", "Tacrolimus", "Cyclophosphamide"), "用於器官移植、自體免疫疾病與部分血液腫瘤情境，需監測感染與器官毒性。"),
    # Hematology: anemia, coagulation, thrombosis, transfusion.
    TopicSeed("condition", "anemia", "Anemia (貧血)", ("Anemia", "貧血", "Hgb", "MCV"), "血紅素或紅血球量下降；初步依 MCV、reticulocyte response 與其他血球變化分類。"),
    TopicSeed("condition", "microcytic-anemia", "Microcytic anemia (小球性貧血)", ("Microcytic anemia", "小球性貧血", "MCV < 80"), "MCV 下降的貧血，常見原因包含缺鐵、thalassemia 與慢性發炎。"),
    TopicSeed("condition", "iron-deficiency-anemia", "Iron deficiency anemia, IDA (缺鐵性貧血)", ("Iron deficiency anemia", "IDA", "缺鐵性貧血", "Ferritin < 15", "TIBC"), "鐵缺乏造成小球性貧血，成人需尋找慢性失血來源。"),
    TopicSeed("condition", "thalassemia", "Thalassemia (地中海型貧血)", ("Thalassemia", "地中海型貧血", "海洋性貧血", "HbA2", "Hb H", "Cooley"), "globin chain 生成異常造成小球性貧血與溶血，依 alpha/beta 與嚴重度分類。"),
    TopicSeed("condition", "anemia-of-chronic-inflammation", "Anemia of chronic inflammation, ACI (慢性發炎性貧血)", ("Anemia of chronic", "ACI", "ACD", "慢性疾病貧血", "慢性發炎性貧血"), "慢性發炎、感染或惡性腫瘤造成鐵利用障礙與造血抑制。"),
    TopicSeed("condition", "macrocytic-anemia", "Macrocytic anemia (大球性貧血)", ("Macrocytic anemia", "大球性貧血", "MCV > 100", "megaloblastic"), "MCV 上升的貧血，常見於 B12/folate deficiency、肝病、酒精或骨髓疾病。"),
    TopicSeed("condition", "megaloblastic-anemia", "Megaloblastic anemia (巨芽細胞性貧血)", ("Megaloblastic anemia", "巨芽細胞", "hypersegmented neutrophil", "B12", "Folate"), "DNA 合成障礙造成大球性貧血與 hypersegmented neutrophils。"),
    TopicSeed("condition", "vitamin-b12-deficiency", "Vitamin B12 deficiency (維生素 B12 缺乏)", ("Vitamin B12", "B12 deficiency", "維生素 B12", "pernicious anemia", "Intrinsic factor"), "B12 缺乏造成 megaloblastic anemia，可合併神經病變。"),
    TopicSeed("condition", "folate-deficiency", "Folate deficiency (葉酸缺乏)", ("Folate deficiency", "葉酸缺乏", "folic acid", "alcohol"), "葉酸缺乏造成 DNA 合成障礙與巨芽細胞性貧血。"),
    TopicSeed("condition", "hemolytic-anemia", "Hemolytic anemia (溶血性貧血)", ("Hemolytic anemia", "溶血性貧血", "LDH", "haptoglobin", "indirect bilirubin"), "紅血球破壞增加造成貧血，常有 reticulocyte 上升、LDH/indirect bilirubin 上升與 haptoglobin 下降。"),
    TopicSeed("condition", "autoimmune-hemolytic-anemia", "Autoimmune hemolytic anemia, AIHA (自體免疫溶血性貧血)", ("Autoimmune hemolytic", "AIHA", "自體免疫溶血", "Coombs", "warm", "cold agglutinin"), "抗紅血球抗體造成免疫性溶血，可依 warm/cold antibody 分類。"),
    TopicSeed("condition", "microangiopathic-hemolytic-anemia", "Microangiopathic hemolytic anemia, MAHA (微血管病變性溶血性貧血)", ("MAHA", "microangiopathic", "fragment RBC", "schistocyte", "微血管病變性溶血"), "微血管血栓或內皮傷害造成 fragment RBC 與溶血。"),
    TopicSeed("condition", "pancytopenia", "Pancytopenia (全血球減少症)", ("Pancytopenia", "全血球減少", "三系血球"), "紅血球、白血球與血小板皆下降，需評估骨髓、脾臟與全身疾病。"),
    TopicSeed("condition", "aplastic-anemia", "Aplastic anemia (再生不良性貧血)", ("Aplastic anemia", "再生不良性貧血", "hypocellular marrow", "ATG"), "骨髓造血細胞減少造成 pancytopenia，治療依嚴重度與移植適合度決定。"),
    TopicSeed("condition", "paroxysmal-nocturnal-hemoglobinuria", "Paroxysmal nocturnal hemoglobinuria, PNH (陣發性夜間血紅素尿症)", ("PNH", "Paroxysmal nocturnal", "陣發性夜間", "CD55", "CD59", "Ham"), "PIGA/GPI-anchor 異常造成補體介導溶血、血栓與骨髓衰竭關聯。"),
    TopicSeed("condition", "immune-thrombocytopenia", "Immune thrombocytopenia, ITP (免疫性血小板低下)", ("ITP", "Immune thrombocytopenic", "免疫性血小板", "Anti-PLT"), "免疫破壞血小板造成 isolated thrombocytopenia，治療依出血與血小板數決定。"),
    TopicSeed("condition", "thrombotic-thrombocytopenic-purpura", "Thrombotic thrombocytopenic purpura, TTP (血栓性血小板低下紫斑症)", ("TTP", "Thrombotic thrombocytopenic", "ADAMTS13", "血栓性血小板低下"), "ADAMTS13 缺乏造成 platelet-vWF microthrombi，可有 MAHA、thrombocytopenia、神經與腎臟表現。"),
    TopicSeed("condition", "disseminated-intravascular-coagulation", "Disseminated intravascular coagulation, DIC (瀰漫性血管內凝血)", ("DIC", "disseminated intravascular", "瀰漫性血管內凝血", "PT", "aPTT", "fibrinogen"), "全身凝血活化造成血栓與出血並存，常由敗血症、癌症、產科或創傷引發。"),
    TopicSeed("condition", "von-willebrand-disease", "Von Willebrand disease, vWD (類血友病)", ("von Willebrand", "vWD", "類血友病", "vWF", "DDAVP"), "vWF 缺乏或功能異常造成 platelet adhesion 缺陷與 factor VIII 穩定性下降。"),
    TopicSeed("condition", "hemophilia-a", "Hemophilia A (A 型血友病)", ("Hemophilia A", "血友病 A", "Factor VIII", "第八因子"), "factor VIII 缺乏造成 intrinsic pathway 異常與深部出血。"),
    TopicSeed("condition", "hemophilia-b", "Hemophilia B (B 型血友病)", ("Hemophilia B", "血友病 B", "Factor IX", "第九因子"), "factor IX 缺乏造成 intrinsic pathway 異常。"),
    TopicSeed("condition", "heparin-induced-thrombocytopenia", "Heparin-induced thrombocytopenia, HIT (肝素誘發血小板低下)", ("HIT", "Heparin-induced", "PF4", "肝素誘發血小板"), "heparin-PF4 抗體造成血小板活化、血小板低下與血栓風險。"),
    TopicSeed("condition", "venous-thromboembolism", "Venous thromboembolism, VTE (靜脈血栓栓塞)", ("VTE", "venous thromboembolism", "DVT", "deep vein thrombosis", "靜脈血栓"), "深部靜脈血栓與肺栓塞屬同一血栓疾病光譜。"),
    TopicSeed("condition", "thrombophilia", "Thrombophilia (血栓傾向)", ("Thrombophilia", "血栓傾向", "Protein C", "Protein S", "Factor V Leiden", "antithrombin"), "先天或後天抗凝失衡造成血栓風險增加。"),
    TopicSeed("condition", "myelodysplastic-syndrome", "Myelodysplastic syndrome, MDS (骨髓發育不良症候群)", ("MDS", "Myelodysplastic", "骨髓發育不良"), "造血幹細胞異常造成無效造血與 cytopenia，可進展為 AML。"),
    TopicSeed("condition", "acute-myeloid-leukemia", "Acute myeloid leukemia, AML (急性骨髓性白血病)", ("AML", "acute myelogenous", "acute myeloid", "急性骨髓", "Auer rod", "MPO"), "骨髓系 blast 增生的急性白血病，治療依 cytogenetics/molecular risk 分層。"),
    TopicSeed("condition", "acute-lymphoblastic-leukemia", "Acute lymphoblastic leukemia, ALL (急性淋巴性白血病)", ("ALL", "acute lymphoblastic", "急性淋巴", "TdT", "CNS prophylaxis"), "淋巴母細胞急性白血病，兒童常見並需 CNS prophylaxis。"),
    TopicSeed("condition", "acute-promyelocytic-leukemia", "Acute promyelocytic leukemia, APL (急性前骨髓性白血病)", ("APL", "acute promyelocytic", "M3", "t(15;17)", "PML-RARA", "ATRA"), "AML 特殊亞型，PML-RARA 造成分化停滯且高度 DIC 風險，ATRA 改善預後。"),
    TopicSeed("condition", "differentiation-syndrome", "Differentiation syndrome (分化症候群)", ("Differentiation syndrome", "retinoic acid syndrome", "分化症候群", "ATRA"), "APL 使用 ATRA/arsenic 等分化治療後可發生發燒、水腫、呼吸窘迫等 capillary leak 表現。"),
    TopicSeed("condition", "chronic-myeloid-leukemia", "Chronic myeloid leukemia, CML (慢性骨髓性白血病)", ("CML", "chronic myeloid", "chronic myelogenous", "慢性骨髓性", "Philadelphia", "BCR-ABL"), "BCR-ABL 相關 myeloproliferative neoplasm，可有 leukocytosis 與 splenomegaly。"),
    TopicSeed("condition", "chronic-lymphocytic-leukemia", "Chronic lymphocytic leukemia, CLL (慢性淋巴性白血病)", ("CLL", "chronic lymphocytic", "慢性淋巴", "smudge cell", "CD5"), "成熟 B cell 腫瘤，常見於老人，可表現淋巴球增多與 smudge cells。"),
    TopicSeed("condition", "myeloproliferative-neoplasms", "Myeloproliferative neoplasms, MPN (骨髓增生性腫瘤)", ("myeloproliferative", "MPN", "CMPD", "骨髓增生"), "造血幹細胞 clonal 增生疾病群，包含 PV、ET、PMF、CML 等。"),
    TopicSeed("condition", "polycythemia-vera", "Polycythemia vera, PV (真性紅血球增多症)", ("Polycythemia vera", "PV", "真性紅血球", "JAK2"), "JAK2 相關紅血球增多性 MPN，增加血栓與轉化風險。"),
    TopicSeed("condition", "essential-thrombocythemia", "Essential thrombocythemia, ET (原發性血小板增多症)", ("Essential thrombocythemia", "ET", "原發性血小板增多", "JAK2"), "血小板為主的 MPN，可有血栓或出血風險。"),
    TopicSeed("condition", "primary-myelofibrosis", "Primary myelofibrosis, PMF (原發性骨髓纖維化)", ("Primary myelofibrosis", "myelofibrosis", "PMF", "骨髓纖維化", "teardrop"), "骨髓纖維化與髓外造血造成脾大、貧血與 teardrop RBC。"),
    TopicSeed("condition", "lymphoma", "Lymphoma (淋巴瘤)", ("Lymphoma", "淋巴瘤", "lymphadenopathy", "B symptoms"), "淋巴系統惡性腫瘤，依 Hodgkin 與 non-Hodgkin 及分子/型態分類。"),
    TopicSeed("condition", "hodgkin-lymphoma", "Hodgkin lymphoma (何杰金氏淋巴瘤)", ("Hodgkin", "何杰金", "Reed-Sternberg", "ABVD"), "具 Reed-Sternberg cells 的淋巴瘤，治療常與 ABVD 化療及放療相關。"),
    TopicSeed("condition", "non-hodgkin-lymphoma", "Non-Hodgkin lymphoma, NHL (非何杰金氏淋巴瘤)", ("Non-Hodgkin", "NHL", "非何杰金", "CHOP"), "多樣化 B/T/NK cell 淋巴瘤疾病群，依侵襲性與細胞來源治療。"),
    TopicSeed("condition", "diffuse-large-b-cell-lymphoma", "Diffuse large B-cell lymphoma, DLBCL (瀰漫性大 B 細胞淋巴瘤)", ("DLBCL", "diffuse large", "瀰漫性大 B"), "侵襲性 B cell lymphoma，常以快速長大淋巴結表現。"),
    TopicSeed("condition", "follicular-lymphoma", "Follicular lymphoma (濾泡性淋巴瘤)", ("Follicular lymphoma", "濾泡性", "t(14;18)", "BCL-2"), "indolent B cell lymphoma，常見 t(14;18)/BCL2。"),
    TopicSeed("condition", "mantle-cell-lymphoma", "Mantle cell lymphoma (被套細胞淋巴瘤)", ("Mantle cell", "被套細胞", "Cyclin D1", "t(11;14)"), "B cell lymphoma，與 cyclin D1 overexpression/t(11;14) 相關。"),
    TopicSeed("condition", "burkitt-lymphoma", "Burkitt lymphoma (伯基特淋巴瘤)", ("Burkitt", "伯基特", "t(8;14)", "c-MYC", "starry sky"), "高度侵襲性 B cell lymphoma，常見 c-MYC translocation。"),
    TopicSeed("condition", "malt-lymphoma", "MALT lymphoma (黏膜相關淋巴組織淋巴瘤)", ("MALT", "mucosa-associated", "黏膜相關淋巴"), "extranodal marginal zone lymphoma，胃部 MALT 常與 H. pylori 相關。"),
    TopicSeed("condition", "multiple-myeloma", "Multiple myeloma, MM (多發性骨髓瘤)", ("Multiple myeloma", "MM", "多發性骨髓瘤", "M protein", "CRAB", "plasma cell"), "漿細胞惡性增生造成 M protein、骨病變、貧血、腎損傷與高血鈣。"),
    TopicSeed("condition", "monoclonal-gammopathy-of-undetermined-significance", "MGUS (意義未明單株免疫球蛋白血症)", ("MGUS", "monoclonal gammopathy", "意義未明單株"), "低量單株免疫球蛋白狀態，可進展為 myeloma 或相關漿細胞疾病。"),
    TopicSeed("condition", "waldenstrom-macroglobulinemia", "Waldenstrom macroglobulinemia (華氏巨球蛋白血症)", ("Waldenstrom", "macroglobulinemia", "巨球蛋白", "IgM"), "淋巴漿細胞性淋巴瘤造成 IgM monoclonal protein 與高黏滯症候群。"),
    TopicSeed("condition", "hyperviscosity-syndrome", "Hyperviscosity syndrome (高黏滯症候群)", ("Hyperviscosity", "高黏滯", "viscosity", "IgM"), "血漿蛋白或細胞成分過高造成黏滯度上升，可有視覺、神經與出血症狀。"),
    TopicSeed("condition", "transfusion-reaction", "Transfusion reaction (輸血反應)", ("transfusion reaction", "輸血反應", "TRALI", "TACO", "hemolytic transfusion"), "輸血相關不良反應包含溶血、發熱、過敏、TRALI、TACO 與感染風險。"),
    TopicSeed("diagnostic", "reticulocyte-production-index", "Reticulocyte production index, RPI (網狀紅血球生成指數)", ("Reticulocyte production index", "RPI", "reticulocyte index", "網狀紅血球"), "校正貧血程度與 reticulocyte 成熟時間後評估骨髓造血反應。"),
    TopicSeed("diagnostic", "iron-studies", "Iron studies (鐵質檢查)", ("iron studies", "Iron profile", "Ferritin", "TIBC", "Transferrin saturation", "鐵質"), "Ferritin、serum iron、TIBC 與 transferrin saturation 協助區分 IDA 與 ACI 等。"),
    TopicSeed("diagnostic", "coombs-test", "Coombs test (庫姆氏試驗)", ("Coombs", "Direct antiglobulin", "Indirect Coombs", "庫姆氏"), "偵測 RBC 表面或血漿抗紅血球抗體，用於 immune hemolysis 與輸血前評估。"),
    TopicSeed("diagnostic", "coagulation-tests", "Coagulation tests, PT/aPTT (凝血檢查)", ("PT", "aPTT", "INR", "凝血", "Bleeding time"), "PT/aPTT/INR 與 platelet/bleeding time pattern 協助區分 primary 與 secondary hemostasis 異常。"),
    TopicSeed("diagnostic", "bone-marrow-examination", "Bone marrow examination (骨髓檢查)", ("bone marrow", "骨髓", "BM biopsy", "aspiration", "blast"), "骨髓抽吸與切片用於 cytopenia、白血病、淋巴瘤、漿細胞疾病與骨髓纖維化評估。"),
    TopicSeed("diagnostic", "flow-cytometry", "Flow cytometry (流式細胞術)", ("Flow cytometry", "流式細胞", "CD marker", "immunophenotype"), "以表面標記與細胞特徵分類白血病、淋巴瘤、PNH 等血液疾病。"),
    TopicSeed("diagnostic", "protein-electrophoresis", "Protein electrophoresis (蛋白電泳)", ("SPEP", "UPEP", "protein electrophoresis", "蛋白電泳", "M spike"), "偵測 monoclonal protein，支援 myeloma、MGUS、Waldenstrom 等診斷。"),
    TopicSeed("procedure", "plasma-exchange", "Plasma exchange, PLEX (血漿置換)", ("Plasma exchange", "plasma exchange", "PLEX", "plasmapheresis", "血漿置換"), "以血漿移除致病抗體或補充缺乏因子，可用於 TTP、GBS、NMO、MG crisis 等疾病。"),
    TopicSeed("procedure", "hematopoietic-stem-cell-transplantation", "Hematopoietic stem cell transplantation, HSCT (造血幹細胞移植)", ("HSCT", "hematopoietic stem cell", "bone marrow transplant", "造血幹細胞", "骨髓移植"), "治療高風險血液惡性腫瘤、骨髓衰竭與部分免疫疾病的細胞治療。"),
    TopicSeed("procedure", "blood-transfusion", "Blood transfusion (輸血)", ("Blood transfusion", "輸血", "packed RBC", "platelet transfusion", "FFP", "cryoprecipitate"), "依 RBC、platelet、FFP、cryoprecipitate 等成分補充氧合能力、止血或凝血因子。"),
    TopicSeed("physiology", "hemostasis", "Hemostasis (止血生理)", ("Hemostasis", "Primary hemostasis", "Secondary hemostasis", "止血", "platelet adhesion", "coagulation cascade"), "止血包含血小板黏附/活化/聚集與凝血因子形成 fibrin clot。"),
    TopicSeed("physiology", "iron-metabolism", "Iron metabolism (鐵代謝)", ("Iron metabolism", "鐵代謝", "Transferrin", "Ferritin", "hepcidin"), "鐵吸收、運輸、儲存與發炎調控決定紅血球生成與 anemia pattern。"),
    TopicSeed("drug", "warfarin", "Warfarin (華法林)", ("Warfarin", "Coumadin", "華法林", "vitamin K epoxide"), "抑制 vitamin K recycling，降低 factor II、VII、IX、X，需以 INR 監測。"),
    TopicSeed("drug", "direct-oral-anticoagulants", "Direct oral anticoagulants, DOACs (直接口服抗凝血劑)", ("DOAC", "NOAC", "direct oral anticoagulant", "apixaban", "rivaroxaban", "dabigatran"), "直接抑制 Xa 或 thrombin 的口服抗凝藥。"),
    TopicSeed("drug", "antiplatelet-drugs", "Antiplatelet drugs (抗血小板藥物)", ("antiplatelet", "抗血小板", "Aspirin", "Clopidogrel", "GP IIb/IIIa"), "抑制 platelet activation 或 aggregation，用於動脈血栓預防與治療。"),
    TopicSeed("drug", "iron-supplementation", "Iron supplementation (鐵劑治療)", ("Ferrous sulfate", "Iron sucrose", "鐵劑", "口服鐵", "靜脈鐵"), "補充鐵以治療 iron deficiency，需依吸收、耐受性與病因選擇路徑。"),
    # Oncology, chemotherapy, palliative/family medicine.
    TopicSeed("condition", "breast-cancer", "Breast cancer (乳癌)", ("Breast cancer", "乳癌", "BRCA", "HER2", "ER", "PR", "DCIS", "LCIS"), "乳房惡性腫瘤，治療依分期、ER/PR/HER2 與病理亞型決定。"),
    TopicSeed("condition", "colorectal-cancer", "Colorectal cancer (大腸直腸癌)", ("Colorectal cancer", "colon cancer", "rectal cancer", "大腸直腸癌", "CEA", "FOLFOX", "FOLFIRI"), "大腸與直腸惡性腫瘤，篩檢、分期與手術/化療策略影響預後。"),
    TopicSeed("condition", "sarcoma", "Sarcoma (肉瘤)", ("Sarcoma", "肉瘤", "soft tissue sarcoma", "osteosarcoma"), "間葉組織惡性腫瘤，治療常需手術、放療與特定化療整合。"),
    TopicSeed("condition", "cancer-of-unknown-primary", "Cancer of unknown primary, CUP (原發不明癌)", ("unknown primary", "CUP", "原發不明", "poorly differentiated carcinoma"), "轉移癌但原發部位未明時，需以病理、免疫染色與臨床線索找來源。"),
    TopicSeed("condition", "paraneoplastic-syndrome", "Paraneoplastic syndrome (腫瘤旁症候群)", ("Paraneoplastic", "腫瘤旁", "SIADH", "PTHrP", "Lambert-Eaton"), "腫瘤以非直接侵犯方式造成內分泌、神經、皮膚或血液異常。"),
    TopicSeed("condition", "tumor-lysis-syndrome", "Tumor lysis syndrome (腫瘤溶解症候群)", ("Tumor lysis", "TLS", "腫瘤溶解", "uric acid", "hyperphosphatemia"), "腫瘤快速破壞造成高尿酸、高血鉀、高血磷、低血鈣與 AKI 風險。"),
    TopicSeed("condition", "superior-vena-cava-syndrome", "Superior vena cava syndrome, SVCS (上腔靜脈症候群)", ("Superior vena cava", "SVC syndrome", "SVCS", "上腔靜脈"), "腫瘤或血栓壓迫/阻塞 SVC 造成臉頸上肢腫脹與靜脈怒張。"),
    TopicSeed("condition", "spinal-cord-compression", "Malignant spinal cord compression (惡性脊髓壓迫)", ("spinal cord compression", "脊髓壓迫", "back pain", "metastasis"), "癌症脊椎轉移壓迫脊髓，需快速辨識與處理以保留神經功能。"),
    TopicSeed("condition", "febrile-neutropenia", "Febrile neutropenia (嗜中性球低下發燒)", ("Febrile neutropenia", "neutropenic fever", "嗜中性球低下發燒", "ANC"), "化療後嗜中性球低下合併發燒是感染急症，需快速經驗性抗生素。"),
    TopicSeed("condition", "chemotherapy-induced-nausea-vomiting", "Chemotherapy-induced nausea and vomiting, CINV (化療引起噁心嘔吐)", ("CINV", "chemotherapy-induced nausea", "化療噁心", "5-HT3", "Ondansetron"), "化療常見副作用，依 emetogenic risk 使用止吐策略。"),
    TopicSeed("condition", "chemotherapy-extravasation", "Chemotherapy extravasation (化療藥物外滲)", ("extravasation", "vesicant", "化療外滲", "冰敷", "熱敷", "Dexrazoxane"), "vesicant 化療外滲可造成組織壞死，處置依藥物類別不同。"),
    TopicSeed("diagnostic", "tumor-staging", "Tumor staging (腫瘤分期)", ("TNM", "tumor staging", "腫瘤分期", "stage"), "腫瘤分期整合原發腫瘤、淋巴結與遠端轉移，決定治療與預後。"),
    TopicSeed("diagnostic", "tumor-markers", "Tumor markers (腫瘤標記)", ("tumor marker", "腫瘤標記", "CEA", "CA-125", "AFP", "CA15-3", "PSA"), "腫瘤標記可用於特定癌症追蹤或輔助診斷，但通常不能單獨診斷癌症。"),
    TopicSeed("diagnostic", "mammography", "Mammography (乳房 X 光攝影)", ("Mammography", "乳房攝影", "乳房 X 光", "microcalcification", "BIRADS"), "乳癌篩檢與診斷影像，特別適合脂肪比例較高的乳房偵測鈣化。"),
    TopicSeed("diagnostic", "bi-rads", "BI-RADS (乳房影像報告與資料系統)", ("BI-RADS", "BIRADS", "乳房影像", "category 0"), "乳房影像標準化分類，指引追加影像、切片或追蹤。"),
    TopicSeed("procedure", "lumpectomy", "Lumpectomy (乳房保留手術)", ("Lumpectomy", "乳房保留", "breast-conserving"), "乳癌局部治療之一，常需搭配放射治療。"),
    TopicSeed("procedure", "mastectomy", "Mastectomy (乳房切除術)", ("Mastectomy", "乳房切除", "modified radical"), "乳癌手術方式之一，依病灶、風險與病人選擇決定範圍。"),
    TopicSeed("procedure", "radiation-therapy", "Radiation therapy (放射治療)", ("Radiation therapy", "放射治療", "radiotherapy", "RT"), "以游離輻射治療局部或區域腫瘤，也可用於症狀緩解。"),
    TopicSeed("drug", "chemotherapy", "Chemotherapy (化學治療)", ("Chemotherapy", "化學治療", "chemo", "cell cycle", "cytotoxic"), "細胞毒性抗癌治療，依 cell-cycle phase 與機轉分類並有特定毒性。"),
    TopicSeed("drug", "alkylating-agents", "Alkylating agents (烷化劑)", ("Alkylating agent", "烷化劑", "Cyclophosphamide", "Ifosfamide", "Melphalan"), "與 DNA cross-linking 相關的化療藥物，常見骨髓抑制、性腺毒性與出血性膀胱炎等。"),
    TopicSeed("drug", "platinum-agents", "Platinum agents (鉑類化療藥)", ("Cisplatin", "Carboplatin", "Oxaliplatin", "Platinum", "鉑類"), "鉑類 DNA-damaging agents，用於肺癌、卵巢癌、大腸癌、生殖細胞瘤等。"),
    TopicSeed("drug", "anthracyclines", "Anthracyclines (蒽環類化療藥)", ("Anthracycline", "Doxorubicin", "Daunorubicin", "Idarubicin", "Epirubicin", "小紅莓"), "抑制 topoisomerase II 並產生自由基，需注意心毒性與外滲傷害。"),
    TopicSeed("drug", "antimetabolites", "Antimetabolites (抗代謝藥物)", ("Antimetabolite", "抗代謝", "5-FU", "Cytarabine", "Gemcitabine", "6-MP", "Pemetrexed"), "干擾 DNA/RNA 合成的化療藥物，多作用於 S phase。"),
    TopicSeed("drug", "topoisomerase-inhibitors", "Topoisomerase inhibitors (拓樸異構酶抑制劑)", ("Topoisomerase", "拓樸異構酶", "Irinotecan", "Etoposide"), "抑制 DNA 拓樸異構酶造成 DNA 損傷，常見於 GI、肺癌與血液腫瘤治療。"),
    TopicSeed("drug", "vinca-alkaloids", "Vinca alkaloids (長春花生物鹼)", ("Vinca", "Vincristine", "Vinblastine", "Vinorelbine", "長春花"), "抑制微小管聚合，常見神經毒性與外滲風險。"),
    TopicSeed("drug", "taxanes", "Taxanes (紫杉醇類)", ("Taxane", "Paclitaxel", "Docetaxel", "紫杉醇"), "穩定微小管、抑制解聚的化療藥，常見過敏、神經毒性與水腫。"),
    TopicSeed("drug", "antiemetics", "Antiemetics (止吐藥)", ("Antiemetic", "止吐", "Ondansetron", "5-HT3", "palonosetron", "Dexamethasone"), "用於預防或治療化療、術後與其他原因的噁心嘔吐。"),
    TopicSeed("drug", "endocrine-therapy-for-breast-cancer", "Endocrine therapy for breast cancer (乳癌荷爾蒙治療)", ("Tamoxifen", "Aromatase inhibitor", "Anastrozole", "Letrozole", "Exemestane", "Fulvestrant", "乳癌荷爾蒙"), "ER/PR positive 乳癌的重要全身治療，依停經狀態與疾病情境選藥。"),
    TopicSeed("drug", "her2-targeted-therapy", "HER2-targeted therapy (HER2 標靶治療)", ("HER2", "Trastuzumab", "Herceptin", "Lapatinib", "HER2-targeted"), "HER2 positive 乳癌等疾病的標靶治療，需注意 trastuzumab 心毒性。"),
    TopicSeed("drug", "bisphosphonates-oncology", "Bisphosphonates in oncology (腫瘤骨病變雙磷酸鹽治療)", ("Bisphosphonate", "Zoledronic", "骨轉移", "skeletal-related"), "腫瘤骨轉移或 myeloma 骨病變可用以降低 skeletal-related events。"),
    TopicSeed("guideline", "cancer-screening", "Cancer screening (癌症篩檢)", ("cancer screening", "癌症篩檢", "mammography", "colonoscopy", "Pap smear", "FOBT"), "針對無症狀族群以年齡與風險分層安排癌症早期偵測。"),
    TopicSeed("guideline", "preventive-medicine", "Preventive medicine (預防醫學)", ("Preventive medicine", "預防醫學", "primary prevention", "secondary prevention", "tertiary prevention"), "以初級、次級、三級預防降低疾病發生、早期偵測與減少失能。"),
    TopicSeed("guideline", "shared-decision-making", "Shared decision making (醫病共同決策)", ("shared decision", "共同決策", "patient preference", "informed consent"), "臨床決策需整合醫療證據、病人價值與可行方案。"),
    TopicSeed("guideline", "dnr", "Do-not-resuscitate, DNR (不施行心肺復甦術)", ("DNR", "do-not-resuscitate", "不施行心肺復甦", "安寧緩和"), "末期或特定情境下不施行 CPR 的預立或代理決策，需依法律與病人意願處理。"),
    TopicSeed("concept", "medical-ethics-four-principles", "Four principles of medical ethics (醫學倫理四原則)", ("autonomy", "beneficence", "nonmaleficence", "justice", "醫學倫理", "四原則"), "尊重自主、行善、不傷害與正義是臨床倫理分析常用框架。"),
    TopicSeed("concept", "spikes-model", "SPIKES model (壞消息告知模型)", ("SPIKES", "壞消息", "breaking bad news", "Setting", "Perception", "Invitation"), "病情告知流程，強調環境、認知、意願、資訊、同理與後續策略。"),
    TopicSeed("concept", "palliative-care", "Palliative care (緩和醫療)", ("Palliative care", "緩和醫療", "安寧", "quality of life", "癌末", "末期病人", "末期醫療"), "以症狀控制、生活品質、溝通與目標照護為核心的全人照護。"),
    TopicSeed("concept", "advance-care-planning", "Advance care planning (預立醫療照護諮商)", ("advance care", "預立醫療", "ACP", "advance directive", "意願書"), "在病情惡化前討論並記錄未來醫療照護偏好。"),
    TopicSeed("concept", "community-medicine", "Community medicine (社區醫學)", ("Community medicine", "社區醫學", "public health", "population health"), "以社區與族群為單位評估健康問題、資源與介入。"),
    TopicSeed("concept", "behavior-change-counseling", "Behavior change counseling (行為改變諮商)", ("behavior change", "行為改變", "motivational interviewing", "5A", "transtheoretical"), "以動機與階段評估協助戒菸、飲食、運動等健康行為改變。"),
)


FIFTH_BOOK_SEEDS: tuple[TopicSeed, ...] = (
    # Pediatrics: congenital heart disease and neonatal cardiopulmonary physiology.
    TopicSeed("condition", "cyanotic-congenital-heart-disease", "Cyanotic congenital heart disease (發紺型先天性心臟病)", ("發紺型先天性心臟病", "cyanotic congenital", "cyanosis", "ductal dependent"), "右到左分流或肺血流不足造成發紺，常需評估 PDA-dependent circulation 與緊急穩定。"),
    TopicSeed("condition", "acyanotic-congenital-heart-disease", "Acyanotic congenital heart disease (非發紺型先天性心臟病)", ("非發紺型先天性心臟病", "acyanotic congenital", "left-to-right shunt"), "左到右分流或出口狹窄的先天性心臟病，表現取決於肺血流與心室負荷。"),
    TopicSeed("condition", "tetralogy-of-fallot", "Tetralogy of Fallot, TOF (法洛氏四合症)", ("Tetralogy of Fallot", "TOF", "法洛", "Tet spell", "boot-shaped"), "最常見發紺型先天性心臟病，包含 VSD、主動脈跨位、右心室出口阻塞與右心室肥大。"),
    TopicSeed("condition", "hypercyanotic-spell", "Hypercyanotic spell / Tet spell (陣發性發紺發作)", ("Tet spell", "hypercyanotic", "陣發性發紺", "knee-chest", "蹲踞"), "TOF 等病童因右心室出口阻塞惡化而突然發紺、躁動與低氧，需快速支持與降低右到左分流。"),
    TopicSeed("condition", "pulmonary-atresia", "Pulmonary atresia (肺動脈閉鎖)", ("Pulmonary atresia", "肺動脈閉鎖", "PA-IVS", "Extreme TOF"), "右心出口完全阻塞，肺血流常依賴 PDA 或 major aortopulmonary collateral arteries。"),
    TopicSeed("condition", "tricuspid-atresia", "Tricuspid atresia (三尖瓣閉鎖)", ("Tricuspid atresia", "三尖瓣閉鎖", "Fontan"), "三尖瓣缺如使全身靜脈血需經 ASD/PFO 分流至左心，常走向單心室循環。"),
    TopicSeed("condition", "transposition-of-great-arteries", "Transposition of the great arteries, TGA (大動脈轉位)", ("Transposition of the great arteries", "TGA", "大動脈轉位", "egg on a string", "arterial switch"), "主動脈與肺動脈連接錯位形成平行循環，需靠 ASD/VSD/PDA 混合血流維持生命。"),
    TopicSeed("condition", "total-anomalous-pulmonary-venous-return", "Total anomalous pulmonary venous return, TAPVR (全肺靜脈回流異常)", ("TAPVR", "Total anomalous pulmonary venous", "全靜脈回流異常", "pulmonary venous obstruction"), "肺靜脈不接入左心房而接入體靜脈系統，可因回流阻塞造成嚴重發紺與肺水腫。"),
    TopicSeed("condition", "ebstein-anomaly", "Ebstein anomaly (Ebstein 異常)", ("Ebstein", "三尖瓣下移", "atrialized right ventricle"), "三尖瓣附著位置下移造成右心房化右心室、三尖瓣逆流與發紺/心律不整風險。"),
    TopicSeed("condition", "hypoplastic-left-heart-syndrome", "Hypoplastic left heart syndrome, HLHS (左心發育不全症候群)", ("HLHS", "Hypoplastic left heart", "左心發育不全", "Norwood"), "左心室與主動脈系統發育不全，體循環依賴 PDA，是 ductal-dependent lesion。"),
    TopicSeed("condition", "ventricular-septal-defect", "Ventricular septal defect, VSD (心室中膈缺損)", ("VSD", "ventricular septal defect", "心室中膈缺損", "holosystolic"), "最常見先天性心臟病之一；分流量取決於缺損大小與肺血管阻力。"),
    TopicSeed("condition", "atrial-septal-defect", "Atrial septal defect, ASD (心房中膈缺損)", ("ASD", "atrial septal defect", "心房中膈缺損", "fixed split S2"), "心房層級左到右分流，常見固定分裂 S2 與右心容量負荷。"),
    TopicSeed("condition", "patent-ductus-arteriosus", "Patent ductus arteriosus, PDA (開放性動脈導管)", ("PDA", "patent ductus arteriosus", "開放性動脈導管", "continuous murmur"), "動脈導管出生後未關閉造成主肺動脈間分流；早產兒與特定先心病情境意義不同。"),
    TopicSeed("condition", "pulmonary-valve-stenosis", "Pulmonary valve stenosis (肺動脈瓣狹窄)", ("Pulmonary valve stenosis", "PVS", "肺動脈瓣狹窄", "pulmonary stenosis"), "右心室出口瓣膜層級狹窄，可造成收縮期雜音、右心室肥大與發紺。"),
    TopicSeed("condition", "coarctation-of-aorta", "Coarctation of the aorta, CoA (主動脈窄縮)", ("Coarctation", "CoA", "主動脈窄縮", "rib notching", "upper lower blood pressure"), "主動脈峽部狹窄造成上下肢血壓差、股動脈脈搏弱與左心負荷增加。"),
    TopicSeed("drug", "prostaglandin-e1", "Prostaglandin E1, PGE1 (前列腺素 E1)", ("PGE1", "Prostaglandin E1", "Alprostadil", "前列腺素", "維持動脈導管"), "用於維持 PDA 開放以穩定 ductal-dependent congenital heart disease。"),
    TopicSeed("procedure", "balloon-atrial-septostomy", "Balloon atrial septostomy, BAS (氣球心房中膈造口術)", ("Balloon atrial septostomy", "BAS", "Rashkind", "心房中膈造口"), "在 TGA 等心房混合不足時擴大心房交通以改善氧合。"),
    TopicSeed("procedure", "fontan-procedure", "Fontan procedure (Fontan 手術)", ("Fontan", "single ventricle", "單心室循環"), "單心室循環的階段性手術終點，使體靜脈血被動進入肺循環。"),
    TopicSeed("procedure", "arterial-switch-operation", "Arterial switch operation (大血管轉位動脈轉位術)", ("arterial switch", "Jatene", "冠狀動脈轉位"), "TGA 的根治手術，將主動脈與肺動脈換回並轉移冠狀動脈。"),
    # Pediatric gastrointestinal, abdominal wall, and hepatobiliary disease.
    TopicSeed("condition", "pediatric-abdominal-pain", "Pediatric abdominal pain (兒童腹痛)", ("兒童腹痛", "Abdominal Pain", "recurrent abdominal pain"), "兒童腹痛鑑別包含感染、外科急症、功能性疾病與腸胃外原因。"),
    TopicSeed("condition", "pediatric-dehydration", "Pediatric dehydration (兒童脫水)", ("脫水", "dehydration", "口服補充液", "oral rehydration"), "兒童腸胃炎常見併發症，需依臨床徵象估計程度並選擇口服或靜脈補液。"),
    TopicSeed("procedure", "oral-rehydration-therapy", "Oral rehydration therapy, ORT (口服補液治療)", ("oral rehydration", "ORT", "口服補液", "ORS"), "以 glucose-sodium cotransport 原理治療輕中度脫水，是兒童急性腸胃炎核心處置。"),
    TopicSeed("condition", "cleft-lip-palate", "Cleft lip and palate (唇顎裂)", ("cleft lip", "cleft palate", "唇顎裂", "顎裂"), "口腔顏面裂隙可影響餵食、語言、牙齒與中耳功能，需多專科照護。"),
    TopicSeed("condition", "esophageal-atresia-tracheoesophageal-fistula", "Esophageal atresia and tracheoesophageal fistula, EA/TEF (食道閉鎖與氣管食道瘻管)", ("esophageal atresia", "tracheoesophageal fistula", "EA/TEF", "食道閉鎖", "食道氣管瘻管"), "新生兒唾液多、嗆咳與無法置入胃管時需懷疑，可合併 VACTERL。"),
    TopicSeed("condition", "hiatal-hernia", "Hiatal hernia (裂孔疝氣)", ("Hiatal hernia", "裂孔疝氣"), "胃食道交界或胃部經橫膈裂孔上移，可與 GERD 表現重疊。"),
    TopicSeed("condition", "hypertrophic-pyloric-stenosis", "Hypertrophic pyloric stenosis, HPS (肥厚性幽門狹窄)", ("Hypertrophic pyloric stenosis", "肥厚性幽門狹窄", "projectile vomiting", "olive-shaped mass"), "嬰兒幽門肌肥厚造成非膽汁性噴射性嘔吐與低氯低鉀代謝性鹼中毒。"),
    TopicSeed("condition", "duodenal-atresia", "Duodenal atresia (十二指腸閉鎖)", ("Duodenal atresia", "十二指腸閉鎖", "double bubble"), "先天十二指腸阻塞造成膽汁性嘔吐與 double-bubble sign，與 Down syndrome 相關。"),
    TopicSeed("condition", "intestinal-malrotation", "Intestinal malrotation (腸旋轉不良)", ("Malrotation", "腸轉位異常", "midgut volvulus", "bilious vomiting"), "中腸旋轉固定異常，可造成 volvulus 與膽汁性嘔吐急症。"),
    TopicSeed("condition", "intussusception", "Intussusception (腸套疊)", ("Intussusception", "腸套疊", "currant jelly", "target sign"), "近端腸道套入遠端腸道，典型有陣發腹痛、嘔吐與果醬便。"),
    TopicSeed("condition", "meckel-diverticulum", "Meckel diverticulum (梅克爾氏憩室)", ("Meckel", "梅克爾", "technetium", "painless bleeding"), "卵黃管殘跡，可因異位胃黏膜造成無痛性下消化道出血。"),
    TopicSeed("condition", "functional-constipation", "Functional constipation (功能性便秘)", ("functional constipation", "功能性便秘", "encopresis"), "兒童常見排便問題，多與疼痛憋便、糞便滯留與行為循環相關。"),
    TopicSeed("condition", "hirschsprung-disease", "Hirschsprung disease (先天性巨結腸症)", ("Hirschsprung", "先天性巨腸", "aganglionic", "megacolon"), "腸神經節細胞缺如造成遠端腸道功能性阻塞，常有胎便延遲。"),
    TopicSeed("condition", "biliary-atresia", "Biliary atresia (膽道閉鎖)", ("Biliary atresia", "膽道閉鎖", "Kasai", "acholic stool"), "嬰兒膽汁鬱積重要病因，需早期辨識灰白便與直接膽紅素上升。"),
    TopicSeed("condition", "omphalocele", "Omphalocele (臍膨出)", ("Omphalocele", "臍膨出"), "腹壁缺損且腸管由膜囊包覆，常合併染色體或其他先天異常。"),
    TopicSeed("condition", "gastroschisis", "Gastroschisis (腹裂)", ("Gastroschisis", "腹裂", "腹裂畸形"), "臍旁腹壁缺損使腸管外露且無膜囊包覆，通常較少合併染色體異常。"),
    # Pediatric renal and urinary disease.
    TopicSeed("condition", "vesicoureteral-reflux", "Vesicoureteral reflux, VUR (膀胱輸尿管逆流)", ("VUR", "vesicoureteral reflux", "膀胱輸尿管逆流", "VCUG"), "膀胱尿液逆流至輸尿管/腎盂，增加反覆 UTI 與腎瘢痕風險。"),
    TopicSeed("condition", "pediatric-hematuria", "Pediatric hematuria (兒童血尿)", ("兒童血尿", "hematuria", "血尿"), "兒童血尿需區分腎絲球性、非腎絲球性、感染、結石與遺傳性腎病。"),
    TopicSeed("condition", "alport-syndrome", "Alport syndrome (亞伯氏症候群)", ("Alport", "亞伯氏", "COL4A", "hearing loss"), "type IV collagen 異常造成遺傳性腎炎，常合併感音性聽損與眼部病變。"),
    TopicSeed("condition", "bartter-syndrome", "Bartter syndrome (Bartter 氏症候群)", ("Bartter", "巴特", "hypokalemic metabolic alkalosis", "NKCC2"), "Henle ascending limb 鹽分再吸收缺陷造成低血鉀代謝性鹼中毒與高 renin/aldosterone。"),
    TopicSeed("condition", "gitelman-syndrome", "Gitelman syndrome (Gitelman 氏症候群)", ("Gitelman", "吉特曼", "hypomagnesemia", "NCC"), "遠曲小管 NCC 缺陷造成低血鉀代謝性鹼中毒、低鎂與低尿鈣。"),
    # Pediatric infections and vaccines.
    TopicSeed("condition", "fever-of-unknown-origin", "Fever of unknown origin, FUO (不明熱)", ("FUO", "fever of unknown origin", "不明熱"), "持續發燒但初步評估未能定位病因，兒童需分層考慮感染、發炎、腫瘤與藥物。"),
    TopicSeed("condition", "acute-otitis-media", "Acute otitis media, AOM (急性中耳炎)", ("acute otitis media", "AOM", "急性中耳炎"), "兒童常見上呼吸道感染併發症，診斷依耳痛、發燒與鼓膜發炎/積液。"),
    TopicSeed("condition", "acute-bacterial-sinusitis", "Acute bacterial sinusitis (急性細菌性鼻竇炎)", ("sinusitis", "鼻竇炎", "acute bacterial sinusitis"), "兒童鼻竇炎需依持續、惡化或嚴重症狀與一般病毒上呼吸道感染區分。"),
    TopicSeed("condition", "epiglottitis", "Epiglottitis (會厭炎)", ("Epiglottitis", "會厭炎", "thumb sign", "drooling", "tripod"), "上呼吸道急症，可快速造成氣道阻塞；Hib 疫苗後盛行率下降。"),
    TopicSeed("condition", "croup", "Croup / laryngotracheobronchitis (哮吼)", ("Croup", "哮吼", "barking cough", "steeple sign"), "多由 parainfluenza 引起的上氣道感染，造成犬吠樣咳嗽與吸氣喘鳴。"),
    TopicSeed("condition", "bronchiolitis", "Bronchiolitis (細支氣管炎)", ("Bronchiolitis", "細支氣管炎", "RSV", "wheezing infant"), "嬰幼兒小氣道病毒感染，RSV 常見，治療多以支持療法為主。"),
    TopicSeed("condition", "parvovirus-b19-infection", "Parvovirus B19 infection (微小病毒 B19 感染)", ("Parvovirus B19", "微小病毒", "fifth disease", "slapped cheek"), "可造成傳染性紅斑、aplastic crisis、胎兒水腫與關節症狀。"),
    TopicSeed("condition", "varicella-zoster-virus-infection", "Varicella-zoster virus infection, VZV (水痘帶狀皰疹病毒感染)", ("VZV", "varicella", "水痘", "帶狀皰疹"), "初感染造成水痘，潛伏再活化造成帶狀皰疹；新生兒與免疫低下族群風險較高。"),
    TopicSeed("condition", "measles", "Measles (麻疹)", ("Measles", "麻疹", "Koplik", "rubeola"), "高度傳染性病毒感染，表現發燒、咳嗽、結膜炎、Koplik spots 與全身斑丘疹。"),
    TopicSeed("condition", "rubella", "Rubella (德國麻疹)", ("Rubella", "德國麻疹", "German measles"), "通常較輕微，但孕期感染可造成 congenital rubella syndrome。"),
    TopicSeed("condition", "enterovirus-infection", "Enterovirus infection (腸病毒感染)", ("Enterovirus", "腸病毒", "hand foot mouth", "herpangina"), "兒童常見病毒感染，可造成手足口病、疱疹性咽峽炎、腦膜炎或心肌炎。"),
    TopicSeed("condition", "adenovirus-infection", "Adenovirus infection (腺病毒感染)", ("Adenovirus", "腺病毒", "pharyngoconjunctival fever"), "可造成咽結膜熱、肺炎、腸胃炎與出血性膀胱炎等多系統感染。"),
    TopicSeed("condition", "epstein-barr-virus-infection", "Epstein-Barr virus infection, EBV (EB 病毒感染)", ("EBV", "Epstein-Barr", "infectious mononucleosis", "異嗜性抗體"), "可造成傳染性單核球增多症，並與部分淋巴瘤、鼻咽癌等疾病相關。"),
    TopicSeed("condition", "herpes-simplex-virus-infection", "Herpes simplex virus infection, HSV (單純皰疹病毒感染)", ("HSV", "Herpes simplex", "單純疱疹", "Tzanck"), "可造成皮膚黏膜病灶、角膜炎、腦炎或新生兒 disseminated infection。"),
    TopicSeed("condition", "roseola-infantum", "Roseola infantum (嬰兒玫瑰疹)", ("Roseola", "嬰兒玫瑰疹", "HHV-6", "exanthem subitum"), "HHV-6/7 造成高燒退後出疹，是嬰幼兒常見病毒疹。"),
    TopicSeed("condition", "cat-scratch-disease", "Cat-scratch disease (貓抓病)", ("Cat-scratch", "貓抓", "Bartonella henselae"), "Bartonella henselae 感染造成局部淋巴結腫大，與貓抓咬暴露相關。"),
    TopicSeed("condition", "scarlet-fever", "Scarlet fever (猩紅熱)", ("Scarlet fever", "猩紅熱", "sandpaper rash", "strawberry tongue"), "A 群鏈球菌毒素造成發燒、咽炎、砂紙樣皮疹與草莓舌。"),
    TopicSeed("condition", "dengue-fever", "Dengue fever (登革熱)", ("Dengue", "登革熱", "breakbone", "登革出血熱"), "蚊媒 flavivirus 感染，可由發燒肌痛進展至 plasma leakage 或出血表現。"),
    TopicSeed("guideline", "pediatric-immunization-schedule", "Pediatric immunization schedule (兒童疫苗接種時程)", ("疫苗接種時間", "immunization schedule", "常規疫苗", "兒童疫苗"), "兒童預防接種依年齡、疫苗種類與特殊情境安排，實務需查當地最新版官方時程。"),
    TopicSeed("guideline", "vaccine-contraindications", "Vaccine contraindications (疫苗禁忌與注意事項)", ("疫苗禁忌", "contraindication", "live vaccine", "anaphylaxis"), "疫苗接種前需評估嚴重過敏、免疫低下、懷孕與急性中重度疾病等禁忌/延後情境。"),
    TopicSeed("drug", "palivizumab", "Palivizumab (RSV 單株抗體預防)", ("Palivizumab", "Synagis", "RSV prophylaxis"), "高風險早產兒或特定心肺疾病嬰兒可用於 RSV 預防；適應症需依當地政策更新。"),
    # Pediatric neurology, development, and behavior.
    TopicSeed("condition", "neurofibromatosis-type-1", "Neurofibromatosis type 1, NF1 (第一型神經纖維瘤症)", ("Neurofibromatosis", "NF1", "神經纖維瘤", "cafe-au-lait", "Lisch"), "RAS pathway 相關神經皮膚症候群，可有 cafe-au-lait spots、neurofibroma、視神經膠質瘤與學習問題。"),
    TopicSeed("condition", "tuberous-sclerosis-complex", "Tuberous sclerosis complex, TSC (結節性硬化症)", ("Tuberous sclerosis", "TSC", "結節性硬化", "ash leaf", "subependymal"), "mTOR pathway 疾病，造成皮膚、腦、腎、心等多器官 hamartoma。"),
    TopicSeed("condition", "sturge-weber-syndrome", "Sturge-Weber syndrome (史德格-韋伯症候群)", ("Sturge-Weber", "史德格", "port-wine stain", "leptomeningeal"), "臉部 port-wine stain 合併 leptomeningeal angioma，可有癲癇、青光眼與神經缺損。"),
    TopicSeed("condition", "von-hippel-lindau-disease", "Von Hippel-Lindau disease, VHL (馮希伯-林道症候群)", ("von Hippel", "VHL", "林道", "hemangioblastoma"), "腫瘤抑制基因疾病，增加 hemangioblastoma、renal cell carcinoma、pheochromocytoma 等風險。"),
    TopicSeed("condition", "myasthenia-gravis", "Myasthenia gravis, MG (重症肌無力)", ("Myasthenia gravis", "MG", "重症肌無力", "acetylcholine receptor"), "神經肌肉接合處自體免疫疾病，造成易疲勞性肌無力與眼肌/吞嚥/呼吸受累。"),
    TopicSeed("condition", "spinal-muscular-atrophy", "Spinal muscular atrophy, SMA (脊髓性肌肉萎縮症)", ("Spinal muscular atrophy", "SMA", "脊髓性肌肉萎縮", "SMN1"), "SMN1 缺陷造成 anterior horn cell degeneration 與對稱性近端肌無力。"),
    TopicSeed("condition", "duchenne-muscular-dystrophy", "Duchenne muscular dystrophy, DMD (杜顯氏肌肉失養症)", ("Duchenne", "DMD", "裘馨", "杜顯", "Gowers", "dystrophin"), "X-linked dystrophin 缺陷造成兒童進行性近端肌無力、CK 升高與心肌病變風險。"),
    TopicSeed("condition", "becker-muscular-dystrophy", "Becker muscular dystrophy, BMD (貝克型肌肉失養症)", ("Becker muscular", "BMD", "貝克型肌肉失養"), "dystrophin partially functional 的較輕型肌肉失養症，發病與進展較 DMD 晚。"),
    TopicSeed("condition", "myotonic-dystrophy", "Myotonic dystrophy (強直性肌肉失養症)", ("Myotonic dystrophy", "強直性肌肉失養", "myotonia", "CTG"), "三核苷酸重複擴增疾病，表現 myotonia、肌無力、白內障、心傳導與內分泌問題。"),
    TopicSeed("condition", "guillain-barre-syndrome", "Guillain-Barre syndrome, GBS (格林-巴利症候群)", ("Guillain", "GBS", "格林", "ascending weakness", "areflexia"), "急性免疫性多發神經根神經病變，常有上升性無力與反射下降。"),
    TopicSeed("condition", "bell-palsy", "Bell palsy (貝爾氏顏面神經麻痺)", ("Bell palsy", "貝爾", "facial palsy"), "急性周邊型顏面神經麻痺，需排除中樞與感染等原因。"),
    TopicSeed("condition", "cerebral-palsy", "Cerebral palsy, CP (腦性麻痺)", ("Cerebral palsy", "CP", "腦性麻痺", "spastic diplegia"), "發育中腦部非進行性傷害造成姿勢與動作障礙，可合併癲癇、認知與吞嚥問題。"),
    TopicSeed("condition", "charcot-marie-tooth-disease", "Charcot-Marie-Tooth disease, CMT (遺傳性運動感覺神經病變)", ("Charcot-Marie-Tooth", "CMT", "hereditary motor and sensory neuropathy", "遺傳性運動"), "遺傳性周邊神經病變，常有遠端肌無力、足部變形與感覺異常。"),
    TopicSeed("condition", "attention-deficit-hyperactivity-disorder", "Attention-deficit/hyperactivity disorder, ADHD (注意力不足過動症)", ("ADHD", "注意力不足", "過動症", "methylphenidate"), "神經發展疾病，核心為不專注、過動與衝動，需跨情境造成明顯功能受損。"),
    TopicSeed("condition", "tourette-syndrome", "Tourette syndrome (妥瑞氏症)", ("Tourette", "妥瑞", "tic", "tics"), "多發動作 tic 加至少一種聲語 tic 且持續超過一年。"),
    TopicSeed("condition", "febrile-seizure", "Febrile seizure (熱痙攣)", ("Febrile seizure", "熱痙攣", "simple febrile", "complex febrile"), "發燒相關兒童癲癇發作，需區分 simple 與 complex 並排除 CNS infection。"),
    TopicSeed("condition", "acute-bacterial-meningitis", "Acute bacterial meningitis (急性細菌性腦膜炎)", ("acute bacterial meningitis", "細菌性腦膜炎", "meningitis", "CSF"), "兒童 CNS 細菌感染急症，診斷依臨床、CSF 與病原檢查，治療需即時。"),
    TopicSeed("diagnostic", "developmental-milestones", "Developmental milestones (兒童發展里程碑)", ("developmental milestone", "神經發展", "行為發展", "0~12 個月", "1~5 歲"), "依年齡追蹤粗動作、細動作、語言、認知與社會互動發展。"),
    # Pediatric endocrine and growth.
    TopicSeed("condition", "congenital-hypothyroidism", "Congenital hypothyroidism (先天性甲狀腺低下)", ("Congenital hypothyroidism", "先天性甲狀腺低下", "newborn screening", "cretinism"), "新生兒篩檢重要疾病，延遲治療會影響神經認知發育。"),
    TopicSeed("condition", "rickets", "Rickets (佝僂症)", ("Rickets", "佝僂症", "vitamin D deficiency", "rachitic rosary"), "生長板礦化不足造成骨骼變形，常與 vitamin D、鈣磷代謝或腎小管疾病相關。"),
    TopicSeed("condition", "congenital-adrenal-hyperplasia", "Congenital adrenal hyperplasia, CAH (先天性腎上腺增生)", ("CAH", "Congenital adrenal hyperplasia", "先天性腎上腺增生", "21-hydroxylase", "17-OHP"), "腎上腺類固醇合成酵素缺陷，常見 21-hydroxylase deficiency，可有鹽分流失與性分化異常。"),
    TopicSeed("condition", "maturity-onset-diabetes-of-the-young", "Maturity-onset diabetes of the young, MODY (青少年發作成年型糖尿病)", ("MODY", "maturity onset diabetes", "青少年發作成年型糖尿病"), "單基因 beta-cell 功能異常造成年輕發病糖尿病，家族史與非典型 type 1/type 2 表現提示。"),
    TopicSeed("condition", "precocious-puberty", "Precocious puberty (性早熟)", ("precocious puberty", "性早熟", "central precocious", "GnRH"), "青春期第二性徵過早出現，需區分 central、peripheral 與正常變異。"),
    TopicSeed("condition", "short-stature", "Short stature (身材矮小)", ("Short stature", "身材矮小", "constitutional growth delay", "familial short stature"), "身高低於同年齡族群預期，需用生長速度、骨齡與家族/內分泌/慢性病因評估。"),
    TopicSeed("diagnostic", "bone-age", "Bone age (骨齡)", ("bone age", "骨齡", "Greulich", "Tanner-Whitehouse"), "以手腕 X 光估計骨成熟度，協助評估性早熟與身材矮小。"),
    TopicSeed("diagnostic", "growth-chart", "Growth chart (生長曲線)", ("growth chart", "生長曲線", "percentile", "height velocity"), "兒童生長評估工具，需連續追蹤身高、體重、頭圍與 growth velocity。"),
    TopicSeed("diagnostic", "tanner-staging", "Tanner staging (Tanner 青春期分期)", ("Tanner", "青春期分期", "sexual maturity rating"), "以乳房/生殖器與陰毛發育分期評估青春期進展。"),
    # Pediatric allergy, immunology, and rheumatology.
    TopicSeed("condition", "primary-immunodeficiency", "Primary immunodeficiency (原發性免疫缺乏)", ("primary immunodeficiency", "先天免疫缺乏", "原發性免疫缺乏", "recurrent infection"), "先天免疫系統缺陷，可依 humoral、cellular、phagocyte、complement 缺陷分類。"),
    TopicSeed("condition", "severe-combined-immunodeficiency", "Severe combined immunodeficiency, SCID (嚴重複合型免疫缺乏)", ("SCID", "severe combined immunodeficiency", "嚴重複合型免疫缺乏", "T cell absent"), "T cell 及常合併 B/NK cell 功能缺陷，嬰兒期嚴重感染且 live vaccine 危險。"),
    TopicSeed("condition", "x-linked-agammaglobulinemia", "X-linked agammaglobulinemia, XLA (X 連鎖無丙種球蛋白血症)", ("XLA", "Bruton", "agammaglobulinemia", "無丙種球蛋白"), "BTK 缺陷造成 B cell 成熟障礙與抗體缺乏，表現反覆細菌感染。"),
    TopicSeed("condition", "selective-iga-deficiency", "Selective IgA deficiency (選擇性 IgA 缺乏)", ("Selective IgA", "IgA deficiency", "選擇性 IgA 缺乏"), "最常見原發性免疫缺乏之一，可無症狀或有呼吸道/腸胃感染與自體免疫關聯。"),
    TopicSeed("condition", "chronic-granulomatous-disease", "Chronic granulomatous disease, CGD (慢性肉芽腫病)", ("CGD", "chronic granulomatous", "慢性肉芽腫", "NADPH oxidase", "catalase positive"), "吞噬細胞 NADPH oxidase 缺陷，易感染 catalase-positive organisms 並形成肉芽腫。"),
    TopicSeed("condition", "wiskott-aldrich-syndrome", "Wiskott-Aldrich syndrome (Wiskott-Aldrich 症候群)", ("Wiskott-Aldrich", "WAS", "eczema thrombocytopenia immunodeficiency"), "X-linked 疾病，典型為 eczema、thrombocytopenia 與 recurrent infections。"),
    TopicSeed("condition", "juvenile-idiopathic-arthritis", "Juvenile idiopathic arthritis, JIA (幼年型特發性關節炎)", ("JIA", "juvenile idiopathic arthritis", "幼年型特發性關節炎", "Still disease"), "兒童慢性發炎性關節炎群，依關節數、全身表現、乾癬與 enthesitis 分型。"),
    # Pediatric hematology and oncology.
    TopicSeed("condition", "sickle-cell-disease", "Sickle cell disease (鐮刀型貧血)", ("Sickle cell", "鐮刀型", "HbS", "vaso-occlusive"), "HbS 聚合造成溶血、血管阻塞危象、感染與器官損傷。"),
    TopicSeed("condition", "evans-syndrome", "Evans syndrome (Evans 症候群)", ("Evans syndrome", "Evans", "AIHA ITP"), "自體免疫溶血性貧血合併免疫性血小板低下，可與免疫失調相關。"),
    TopicSeed("condition", "pediatric-brain-tumor", "Pediatric brain tumor (兒童腦瘤)", ("Pediatric Brain Tumor", "兒童腦瘤", "posterior fossa", "medulloblastoma"), "兒童常見實體腫瘤之一，表現依腫瘤位置與顱內壓變化。"),
    TopicSeed("condition", "wilms-tumor", "Wilms tumor (威爾姆氏腫瘤)", ("Wilms", "nephroblastoma", "威爾姆", "WT1"), "兒童腎臟惡性腫瘤，常以無痛腹部腫塊或血尿/高血壓表現。"),
    TopicSeed("condition", "neuroblastoma", "Neuroblastoma (神經母細胞瘤)", ("Neuroblastoma", "神經母細胞瘤", "N-myc", "catecholamine", "VMA", "HVA"), "交感神經系統胚胎性腫瘤，可分泌 catecholamines 並造成腹部腫塊或轉移症狀。"),
    TopicSeed("condition", "hepatoblastoma", "Hepatoblastoma (肝母細胞瘤)", ("Hepatoblastoma", "肝母細胞瘤", "AFP"), "幼兒最常見肝臟惡性腫瘤，常見 AFP 升高與腹部腫塊。"),
    TopicSeed("condition", "retinoblastoma", "Retinoblastoma (視網膜母細胞瘤)", ("Retinoblastoma", "視網膜母細胞瘤", "leukocoria", "RB1"), "RB1 相關兒童眼內惡性腫瘤，典型表現為 leukocoria。"),
    TopicSeed("condition", "osteosarcoma", "Osteosarcoma (骨肉瘤)", ("Osteosarcoma", "骨肉瘤", "sunburst", "Codman"), "青少年常見骨惡性腫瘤，好發長骨 metaphysis，可有疼痛與腫塊。"),
    TopicSeed("condition", "ewing-sarcoma", "Ewing sarcoma (尤文氏肉瘤)", ("Ewing", "尤文", "Ewing Sarcoma", "onion skin", "t(11;22)"), "兒童/青少年小圓藍細胞骨或軟組織腫瘤，常與 EWSR1 translocation 相關。"),
    TopicSeed("condition", "teratoma", "Teratoma (畸胎瘤)", ("Teratoma", "畸胎瘤", "sacrococcygeal"), "含多胚層組織的 germ cell tumor，新生兒常見部位包含 sacrococcygeal region。"),
    # Genetics, metabolic disease, and newborn screening.
    TopicSeed("concept", "newborn-screening", "Newborn screening (新生兒篩檢)", ("newborn screening", "新生兒篩檢", "heel stick"), "以早期檢測可治療或需早期介入的先天代謝、內分泌與其他疾病。"),
    TopicSeed("condition", "inborn-errors-of-metabolism", "Inborn errors of metabolism (先天性代謝異常)", ("inborn error", "先天性代謝", "metabolic disease", "aminoacidopathy", "organic acidemia"), "酵素或運輸蛋白缺陷造成代謝物累積或能量生成障礙，常以餵食差、嘔吐、嗜睡、酸中毒或低血糖表現。"),
    TopicSeed("condition", "phenylketonuria", "Phenylketonuria, PKU (苯酮尿症)", ("Phenylketonuria", "PKU", "苯酮尿症", "phenylalanine"), "phenylalanine hydroxylase 或 BH4 代謝異常造成 phenylalanine 升高，需飲食控制避免神經傷害。"),
    TopicSeed("condition", "galactosemia", "Galactosemia (半乳糖血症)", ("Galactosemia", "半乳糖血症", "GALT", "reducing substance"), "半乳糖代謝缺陷可造成新生兒肝病、敗血症、白內障與餵食問題。"),
    TopicSeed("condition", "methylmalonic-acidemia", "Methylmalonic acidemia (甲基丙二酸血症)", ("Methylmalonic acidemia", "MMA", "甲基丙二酸"), "有機酸血症之一，可造成代謝性酸中毒、酮症、嗜睡與高氨血症。"),
    TopicSeed("condition", "glycogen-storage-disease", "Glycogen storage disease, GSD (肝醣儲積症)", ("Glycogen storage", "GSD", "肝醣儲積症", "Von Gierke", "Pompe"), "肝醣合成或分解酵素缺陷造成低血糖、肝腫大、肌病或心肌病等分型表現。"),
    TopicSeed("condition", "mitochondrial-disease", "Mitochondrial disease (粒線體疾病)", ("mitochondrial disease", "粒線體疾病", "MELAS", "MERRF"), "粒線體 DNA 或核基因缺陷造成多系統能量代謝疾病，常侵犯神經肌肉。"),
    TopicSeed("condition", "trisomy-18", "Trisomy 18 / Edwards syndrome (愛德華氏症)", ("Trisomy 18", "Edwards", "愛德華"), "第 18 對染色體三體症，常有生長遲滯、手指重疊、心臟缺陷與高死亡率。"),
    TopicSeed("condition", "down-syndrome", "Down syndrome / Trisomy 21 (唐氏症)", ("Down syndrome", "Trisomy 21", "唐氏症", "trisomy 21"), "第 21 對染色體三體症，與先天心臟病、腸胃道異常、甲狀腺與血液疾病風險相關。"),
    TopicSeed("condition", "fragile-x-syndrome", "Fragile X syndrome (脆折 X 症候群)", ("Fragile X", "脆折 X", "FMR1", "CGG"), "FMR1 CGG repeat expansion 造成智能障礙、自閉特徵與長臉大耳等表現。"),
    TopicSeed("condition", "digeorge-syndrome", "DiGeorge syndrome / 22q11.2 deletion syndrome (DiGeorge 症候群)", ("DiGeorge", "22q11", "CATCH 22", "thymic aplasia"), "22q11.2 deletion 可造成心臟缺陷、低鈣、胸腺發育不全、顎裂與學習/精神問題。"),
    TopicSeed("condition", "marfan-syndrome", "Marfan syndrome (馬凡氏症候群)", ("Marfan", "馬凡", "FBN1", "aortic root"), "FBN1 異常造成結締組織疾病，侵犯骨骼、眼與主動脈根部。"),
    TopicSeed("condition", "wilson-disease", "Wilson disease (威爾森氏病)", ("Wilson disease", "威爾森", "ATP7B", "Kayser-Fleischer", "ceruloplasmin"), "銅代謝異常造成肝病、神經精神症狀與 Kayser-Fleischer rings。"),
    TopicSeed("condition", "turner-syndrome", "Turner syndrome (透納氏症)", ("Turner syndrome", "透納", "45,X", "webbed neck"), "女性 X 染色體缺失/嵌合，表現身材矮小、性腺發育不全、蹼頸與心腎異常。"),
    TopicSeed("condition", "noonan-syndrome", "Noonan syndrome (努南氏症候群)", ("Noonan", "努南", "PTPN11", "pulmonary valve stenosis"), "RASopathy，表現短身材、特殊臉型、肺動脈瓣狹窄、胸廓異常與凝血問題。"),
    # Neonatology.
    TopicSeed("condition", "congenital-infection", "Congenital infection (先天性感染)", ("congenital infection", "先天性感染", "vertical infection", "perinatal infection"), "母胎或周產期感染造成胎兒/新生兒疾病，需依病原與孕期時點判讀。"),
    TopicSeed("condition", "torch-infections", "TORCH infections (TORCH 先天性感染)", ("TORCH", "Toxoplasmosis", "Rubella", "CMV", "Herpes", "先天性感染"), "Toxoplasma、other、rubella、CMV、HSV 等先天感染群，可造成 IUGR、肝脾腫大、黃疸、神經與眼耳病變。"),
    TopicSeed("condition", "congenital-cmv-infection", "Congenital cytomegalovirus infection (先天性巨細胞病毒感染)", ("congenital CMV", "先天性巨細胞病毒", "periventricular calcification", "sensorineural hearing loss"), "最常見先天病毒感染之一，可有小頭、腦室周圍鈣化、聽損、血小板低下與肝脾腫大。"),
    TopicSeed("condition", "congenital-toxoplasmosis", "Congenital toxoplasmosis (先天性弓漿蟲感染)", ("congenital toxoplasmosis", "弓漿蟲", "chorioretinitis", "hydrocephalus"), "典型三徵為 chorioretinitis、hydrocephalus、intracranial calcifications。"),
    TopicSeed("condition", "congenital-rubella-syndrome", "Congenital rubella syndrome (先天性德國麻疹症候群)", ("congenital rubella", "先天性德國麻疹", "cataract", "PDA", "deafness"), "孕期 rubella 感染造成白內障、PDA/肺動脈狹窄、聽損與發育問題。"),
    TopicSeed("condition", "neonatal-herpes", "Neonatal herpes simplex infection (新生兒單純皰疹感染)", ("neonatal herpes", "新生兒疱疹", "HSV", "skin eye mouth", "disseminated"), "新生兒 HSV 可表現為 skin-eye-mouth disease、CNS disease 或 disseminated disease。"),
    TopicSeed("condition", "neonatal-respiratory-distress-syndrome", "Neonatal respiratory distress syndrome, RDS (新生兒呼吸窘迫症候群)", ("neonatal RDS", "Respiratory distress syndrome", "新生兒呼吸窘迫", "hyaline membrane", "surfactant deficiency"), "早產兒 surfactant deficiency 造成肺泡塌陷、低氧與 hyaline membrane disease。"),
    TopicSeed("condition", "transient-tachypnea-of-newborn", "Transient tachypnea of the newborn, TTN (新生兒暫時性呼吸急促)", ("TTN", "Transient tachypnea", "新生兒暫時性呼吸急促", "retained lung fluid"), "出生後肺液清除延遲造成短暫呼吸急促，常見於剖腹產或早產晚期。"),
    TopicSeed("condition", "apnea-of-prematurity", "Apnea of prematurity (早產兒呼吸暫停)", ("Apnea of prematurity", "早產兒呼吸暫停", "caffeine"), "早產兒呼吸控制未成熟造成呼吸暫停、心搏過慢或低氧。"),
    TopicSeed("condition", "persistent-pulmonary-hypertension-of-newborn", "Persistent pulmonary hypertension of the newborn, PPHN (新生兒持續性肺高壓)", ("PPHN", "persistent pulmonary hypertension", "新生兒持續性肺高壓"), "出生後肺血管阻力未正常下降造成右到左分流與嚴重低氧。"),
    TopicSeed("condition", "meconium-aspiration-syndrome", "Meconium aspiration syndrome (胎便吸入症候群)", ("meconium aspiration", "胎便吸入", "吸入性症候群"), "胎便污染羊水被吸入造成氣道阻塞、化學性肺炎與 PPHN 風險。"),
    TopicSeed("condition", "congenital-diaphragmatic-hernia", "Congenital diaphragmatic hernia, CDH (先天性橫膈膜疝氣)", ("Congenital diaphragmatic hernia", "CDH", "先天性橫膈膜疝氣", "Bochdalek"), "橫膈缺損造成腹腔器官進入胸腔、肺發育不全與新生兒呼吸衰竭。"),
    TopicSeed("diagnostic", "apgar-score", "Apgar score (Apgar 評分)", ("Apgar", "Apgar score", "新生兒評分"), "出生後快速評估 heart rate、respiration、tone、reflex irritability 與 color。"),
    TopicSeed("condition", "neonatal-jaundice", "Neonatal jaundice (新生兒黃疸)", ("neonatal jaundice", "新生兒黃疸", "新生兒高黃疸", "kernicterus", "核黃疸"), "新生兒膽紅素上升可為生理性或病理性，需依日齡、風險因子與直接/間接 bilirubin 判讀。"),
    TopicSeed("procedure", "phototherapy", "Phototherapy (新生兒黃疸照光治療)", ("phototherapy", "照光", "blue light", "新生兒黃疸"), "以藍光將 unconjugated bilirubin 轉為可排泄異構物，降低 kernicterus 風險。"),
    TopicSeed("procedure", "exchange-transfusion", "Exchange transfusion (換血治療)", ("exchange transfusion", "換血", "核黃疸", "severe hyperbilirubinemia"), "嚴重高膽紅素血症或溶血風險時移除 bilirubin 與抗體的高風險處置。"),
    TopicSeed("procedure", "surfactant-therapy", "Surfactant therapy (肺表面張力素治療)", ("surfactant therapy", "表面張力素", "肺泡張力素"), "新生兒 RDS 可補充 exogenous surfactant 改善肺泡穩定與氧合。"),
)


SIXTH_BOOK_SEEDS: tuple[TopicSeed, ...] = (
    # Dermatology: skin structure, physiology, morphology, and bedside tests.
    TopicSeed("anatomy", "skin", "Skin (皮膚)", ("皮膚", "skin", "epidermis", "dermis", "subcutaneous tissue"), "身體最大器官，由 epidermis、dermis、subcutaneous tissue 與附屬器官構成。"),
    TopicSeed("anatomy", "epidermis", "Epidermis (表皮)", ("epidermis", "表皮", "stratum corneum", "stratum spinosum", "stratum basale"), "表皮由角質細胞分化層構成，提供屏障、防水、免疫與色素保護。"),
    TopicSeed("anatomy", "dermis", "Dermis (真皮)", ("dermis", "真皮", "papillary dermis", "reticular dermis"), "真皮含膠原、彈性纖維、血管、神經與附屬器官，決定皮膚強度與彈性。"),
    TopicSeed("anatomy", "skin-appendages", "Skin appendages (皮膚附屬器官)", ("appendages", "毛囊", "皮脂腺", "汗腺", "指甲", "hair follicle"), "毛髮、皮脂腺、汗腺與指甲等附屬器官參與保護、體溫調節與疾病表現。"),
    TopicSeed("physiology", "skin-barrier-function", "Skin barrier function (皮膚屏障功能)", ("skin barrier", "皮膚屏障", "角質層", "ceramide", "Natural Moisturizing Factor"), "角質層、脂質與免疫細胞共同減少水分散失並抵禦外界刺激與病原。"),
    TopicSeed("physiology", "hair-growth-cycle", "Hair growth cycle (毛髮生長週期)", ("anagen", "catagen", "telogen", "毛囊生長", "生長期", "休止期"), "毛囊依 anagen、catagen、telogen 循環，影響掉髮與毛髮疾病判讀。"),
    TopicSeed("concept", "primary-skin-lesions", "Primary skin lesions (基本皮膚病灶)", ("macule", "patch", "papule", "plaque", "nodule", "wheal", "vesicle", "bulla", "皮膚病灶"), "以斑、片、丘疹、斑塊、結節、膨疹、水泡等形態描述皮膚病灶。"),
    TopicSeed("concept", "secondary-skin-lesions", "Secondary skin lesions (次發性皮膚病灶)", ("pustule", "crust", "scale", "erosion", "ulcer", "scar", "atrophy", "膿疱", "鱗屑"), "膿疱、痂、鱗屑、糜爛、潰瘍、疤痕與萎縮反映病程與破壞深度。"),
    TopicSeed("diagnostic", "nikolsky-sign", "Nikolsky sign (Nikolsky 徵象)", ("Nikolsky", "表皮脫落", "水泡邊緣"), "輕壓或摩擦使表皮剝離，見於 SSSS、pemphigus vulgaris、TEN 等表皮內或表皮壞死疾病。"),
    TopicSeed("diagnostic", "wood-lamp-examination", "Wood lamp examination (伍氏燈檢查)", ("Wood lamp", "伍氏燈", "fluorescence"), "紫外光輔助辨識 erythrasma、pityriasis versicolor、部分 tinea 與色素異常。"),
    TopicSeed("diagnostic", "koh-preparation", "KOH preparation (KOH 鏡檢)", ("KOH", "potassium hydroxide", "氫氧化鉀", "fungal hyphae"), "以 KOH 溶解角質後鏡檢菌絲或酵母型態，常用於皮癬菌與念珠菌感染。"),
    TopicSeed("diagnostic", "tzanck-smear", "Tzanck smear (Tzanck 抹片)", ("Tzanck", "multinucleated giant cell", "抹片"), "水泡底部刮取細胞檢查，可見 herpesvirus 感染的 multinucleated giant cells。"),
    TopicSeed("diagnostic", "patch-test", "Patch test (貼布試驗)", ("patch test", "貼布試驗", "contact dermatitis"), "延遲型過敏測試，用於 allergic contact dermatitis 過敏原評估。"),
    # Infectious dermatology.
    TopicSeed("condition", "staphylococcal-scalded-skin-syndrome", "Staphylococcal scalded skin syndrome, SSSS (葡萄球菌性燙傷樣皮膚症候群)", ("SSSS", "staphylococcal scalded", "葡萄球菌性燙傷", "exfoliatin", "desmoglein 1"), "S. aureus exfoliative toxin 裂解 desmoglein 1，造成嬰幼兒表皮淺層剝離且通常不侵犯黏膜。"),
    TopicSeed("condition", "toxic-shock-syndrome", "Toxic shock syndrome, TSS (中毒性休克症候群)", ("Toxic shock syndrome", "TSS", "中毒性休克", "TSST-1", "superantigen"), "S. aureus 或 Group A Streptococcus superantigen 造成發燒、低血壓、紅疹、脫屑與多器官受累。"),
    TopicSeed("condition", "ecthyma", "Ecthyma (臁瘡)", ("Ecthyma", "臁瘡"), "較深層的 impetigo 型感染，侵犯至真皮可形成潰瘍與疤痕。"),
    TopicSeed("condition", "furuncle", "Furuncle (癤)", ("Furuncle", "癤", "boil", "hair follicle abscess"), "毛囊及周邊組織的深部化膿性感染，常由 S. aureus 引起。"),
    TopicSeed("condition", "carbuncle", "Carbuncle (癰)", ("Carbuncle", "癰", "multiple furuncles"), "多個 furuncles 融合形成較深廣的膿瘍性皮膚感染。"),
    TopicSeed("condition", "erythrasma", "Erythrasma (紅癬)", ("Erythrasma", "紅癬", "Corynebacterium minutissimum", "coral-red"), "Corynebacterium minutissimum 表淺感染，伍氏燈可呈 coral-red fluorescence。"),
    TopicSeed("condition", "herpes-zoster", "Herpes zoster (帶狀皰疹)", ("Herpes zoster", "帶狀疱疹", "shingles", "dermatome"), "VZV 再活化沿皮節產生疼痛性群聚水泡，可有眼帶狀皰疹與 postherpetic neuralgia。"),
    TopicSeed("condition", "verruca", "Verruca / warts (疣)", ("Verruca", "warts", "疣", "HPV"), "HPV 感染造成表皮增生性病灶，依部位可為尋常疣、扁平疣、足底疣或尖圭濕疣。"),
    TopicSeed("condition", "molluscum-contagiosum", "Molluscum contagiosum (傳染性軟疣)", ("Molluscum", "傳染性軟疣", "umbilicated papule"), "poxvirus 感染造成中央臍凹丘疹，兒童與免疫低下者較常見。"),
    TopicSeed("condition", "scabies", "Scabies (疥瘡)", ("Scabies", "疥瘡", "Sarcoptes", "burrow"), "Sarcoptes scabiei 寄生造成夜間劇癢與 burrows，常需同住接觸者一起治療。"),
    TopicSeed("condition", "cutaneous-larva-migrans", "Cutaneous larva migrans (皮膚幼蟲移行症)", ("Cutaneous larva migrans", "皮膚幼蟲移行", "creeping eruption"), "動物鉤蟲幼蟲在表皮內移行造成 serpiginous pruritic tracks。"),
    TopicSeed("condition", "dermatophytosis", "Dermatophytosis / tinea (皮癬菌症)", ("Dermatophytosis", "tinea", "皮癬菌", "ringworm"), "皮癬菌感染角質層、毛髮或指甲，依部位命名如 tinea corporis、pedis、capitis。"),
    TopicSeed("condition", "pityriasis-versicolor", "Pityriasis versicolor (變色糠疹／汗斑)", ("Pityriasis versicolor", "Tinea versicolor", "汗斑", "Malassezia"), "Malassezia 造成色素改變與細屑，KOH 可見 spaghetti-and-meatballs。"),
    TopicSeed("condition", "chromoblastomycosis", "Chromoblastomycosis (黑色真菌症)", ("Chromoblastomycosis", "chromomycosis", "黑色真菌症", "sclerotic bodies"), "深部皮膚真菌感染，常與外傷植入有關，可見 muriform/sclerotic bodies。"),
    # Blistering, interface, dermatitis, psoriasis, and drug eruptions.
    TopicSeed("condition", "pemphigus-vulgaris", "Pemphigus vulgaris (尋常性天疱瘡)", ("尋常性天疱瘡", "pemphigus vulgaris", "desmoglein 3", "flaccid bullae"), "抗 desmoglein 自體抗體造成表皮內棘融解與鬆弛水泡，常侵犯黏膜。"),
    TopicSeed("condition", "bullous-pemphigoid", "Bullous pemphigoid (類天疱瘡)", ("Bullous pemphigoid", "類天疱瘡", "BP180", "BP230", "tense bullae"), "抗 hemidesmosome 自體抗體造成表皮下緊繃水泡，多見於老人。"),
    TopicSeed("condition", "paraneoplastic-pemphigus", "Paraneoplastic pemphigus (腫瘤旁天疱瘡)", ("Paraneoplastic pemphigus", "腫瘤旁天疱瘡"), "與惡性腫瘤相關的嚴重黏膜皮膚水泡病，可合併多型抗體與肺部受累。"),
    TopicSeed("condition", "dermatitis-herpetiformis", "Dermatitis herpetiformis (疱疹樣皮膚炎)", ("Dermatitis herpetiformis", "疱疹樣皮膚炎", "IgA", "celiac"), "與 celiac disease 相關，伸側劇癢群聚丘疹水泡，真皮乳突 IgA 沉積。"),
    TopicSeed("condition", "porphyria-cutanea-tarda", "Porphyria cutanea tarda, PCT (緩發性皮膚病變紫質症)", ("Porphyria cutanea tarda", "PCT", "緩發性皮膚病變紫質症", "uroporphyrinogen decarboxylase"), "光曝露部位脆弱水泡與色素改變，與 porphyrin metabolism、肝病、酒精或鐵負荷相關。"),
    TopicSeed("condition", "linear-iga-bullous-dermatosis", "Linear IgA bullous dermatosis (線狀 IgA 水泡病)", ("Linear IgA", "線狀 IgA", "bullous dermatosis"), "基底膜帶線狀 IgA 沉積造成表皮下水泡，可與藥物或兒童慢性水泡病相關。"),
    TopicSeed("condition", "graft-versus-host-disease", "Graft-versus-host disease, GVHD (移植物抗宿主疾病)", ("GVHD", "graft-versus-host", "移植體對抗宿主", "移植物抗宿主"), "移植後 donor immune cells 攻擊 recipient 組織，可侵犯皮膚、腸胃與肝臟。"),
    TopicSeed("condition", "leukocytoclastic-vasculitis", "Leukocytoclastic vasculitis (白血球碎裂性血管炎)", ("leukocytoclastic", "hypersensitivity vasculitis", "過敏性血管炎", "palpable purpura"), "小血管免疫複合物血管炎，皮膚常見 palpable purpura。"),
    TopicSeed("condition", "contact-dermatitis", "Contact dermatitis (接觸性皮膚炎)", ("Contact dermatitis", "接觸性皮膚炎", "irritant", "allergic contact"), "外界物質造成刺激性或 allergic delayed-type 皮膚炎，分布常反映接觸型態。"),
    TopicSeed("condition", "atopic-dermatitis", "Atopic dermatitis (異位性皮膚炎)", ("Atopic dermatitis", "異位性皮膚炎", "eczema", "filaggrin"), "慢性搔癢濕疹性疾病，與皮膚屏障異常、Th2 inflammation 與 atopy 相關。"),
    TopicSeed("condition", "seborrheic-dermatitis", "Seborrheic dermatitis (脂漏性皮膚炎)", ("Seborrheic dermatitis", "脂漏性皮膚炎", "dandruff", "Malassezia"), "皮脂豐富部位的慢性發炎與鱗屑，與 Malassezia 與皮脂環境相關。"),
    TopicSeed("condition", "asteatotic-eczema", "Asteatotic eczema (缺脂性皮膚炎)", ("Asteatotic eczema", "缺脂性皮膚炎", "xerotic eczema"), "皮膚乾燥與屏障破壞造成龜裂、癢與濕疹樣變化。"),
    TopicSeed("condition", "lichen-planus", "Lichen planus (扁平苔癬)", ("Lichen planus", "扁平苔癬", "Wickham striae", "polygonal pruritic purple"), "T cell-mediated interface dermatitis，典型為紫色多角形搔癢丘疹與 Wickham striae。"),
    TopicSeed("condition", "pityriasis-alba", "Pityriasis alba (白色糠疹)", ("Pityriasis alba", "白色糠疹"), "兒童常見低色素細屑斑，與異位性體質或輕度 eczema 相關。"),
    TopicSeed("condition", "fixed-drug-eruption", "Fixed drug eruption (固定性藥物疹)", ("Fixed drug eruption", "固定性藥物疹", "same site"), "藥物再暴露時在相同部位復發的界線清楚紅斑或水泡，癒後可留色素沉著。"),
    TopicSeed("condition", "erythema-nodosum", "Erythema nodosum (結節性紅斑)", ("Erythema nodosum", "結節性紅斑", "tender nodules", "pretibial"), "脂肪隔膜性 panniculitis，常見脛前疼痛結節，需評估感染、藥物、IBD、sarcoidosis 等誘因。"),
    TopicSeed("condition", "stevens-johnson-syndrome-toxic-epidermal-necrolysis", "Stevens-Johnson syndrome / toxic epidermal necrolysis, SJS/TEN (史蒂芬強森症候群／毒性表皮壞死溶解症)", ("SJS", "TEN", "Stevens-Johnson", "toxic epidermal necrolysis", "毒性表皮壞死"), "嚴重藥物或感染相關黏膜皮膚反應，表皮壞死剝離且可危及生命。"),
    TopicSeed("condition", "psoriasis", "Psoriasis (乾癬)", ("Psoriasis", "乾癬", "Auspitz", "Koebner", "silvery scale"), "慢性免疫介導角質增生疾病，典型為紅色斑塊與銀白色鱗屑，可有關節炎與多型態表現。"),
    # Pigmentary disorders and benign/malignant growths.
    TopicSeed("condition", "melanocytic-nevus", "Melanocytic nevus (黑色素細胞痣)", ("nevus", "痣", "melanocytic nevus", "ABCDE"), "黑色素細胞良性增生，需與 melanoma 依 ABCDE 等特徵鑑別。"),
    TopicSeed("condition", "nevus-of-ota", "Nevus of Ota (太田母斑)", ("Nevus of Ota", "太田氏母斑", "oculodermal melanocytosis"), "三叉神經 V1/V2 分布的真皮黑色素增生，可侵犯眼部。"),
    TopicSeed("condition", "freckle", "Freckle / ephelis (雀斑)", ("Freckle", "雀斑", "ephelis"), "日曬相關小型淡褐色斑，黑色素增加但 melanocyte 數量不一定增加。"),
    TopicSeed("condition", "solar-lentigo", "Solar lentigo (曬斑)", ("Solar lentigo", "曬斑", "lentigines"), "慢性日曬造成的界線清楚褐色斑，常見於老年與曝曬部位。"),
    TopicSeed("condition", "melasma", "Melasma / chloasma (肝斑)", ("Melasma", "Chloasma", "肝斑"), "臉部對稱性色素沉著，與紫外線、荷爾蒙、懷孕或藥物相關。"),
    TopicSeed("condition", "albinism", "Albinism (白化症)", ("Albinism", "白化症", "tyrosinase"), "黑色素合成或運輸異常造成皮膚、毛髮、眼部色素不足與光傷害風險。"),
    TopicSeed("condition", "vitiligo", "Vitiligo (白斑)", ("Vitiligo", "白斑", "depigmented", "autoimmune melanocyte"), "後天黑色素細胞破壞造成明顯 depigmented patches，可與自體免疫疾病相關。"),
    TopicSeed("condition", "infantile-hemangioma", "Infantile hemangioma (嬰兒血管瘤)", ("Infantile hemangioma", "嬰兒血管瘤", "strawberry hemangioma", "propranolol"), "嬰兒期血管增生性腫瘤，多數先增生後退化；危及功能或潰瘍時需治療。"),
    TopicSeed("condition", "port-wine-stain", "Port-wine stain (葡萄酒斑)", ("Port-wine stain", "葡萄酒斑", "capillary malformation"), "先天 capillary malformation，可與 Sturge-Weber syndrome 相關。"),
    TopicSeed("condition", "pyogenic-granuloma", "Pyogenic granuloma (化膿性肉芽腫)", ("Pyogenic granuloma", "化膿性肉芽腫", "lobular capillary hemangioma"), "易出血的 lobular capillary hemangioma，常與外傷、懷孕或藥物相關。"),
    TopicSeed("condition", "syringoma", "Syringoma (汗管瘤)", ("Syringoma", "汗管瘤"), "小汗腺導管良性腫瘤，常見於眼周小丘疹。"),
    TopicSeed("condition", "seborrheic-keratosis", "Seborrheic keratosis (脂漏性角化症)", ("Seborrheic keratosis", "脂漏性角化症", "stuck-on"), "常見良性表皮增生，呈 stuck-on waxy papules/plaques。"),
    TopicSeed("condition", "actinic-keratosis", "Actinic keratosis (光化性角化症)", ("Actinic keratosis", "光化性角化症", "solar keratosis"), "日曬造成的鱗屑粗糙角化病灶，是 SCC 前驅病變。"),
    TopicSeed("condition", "arsenical-keratosis", "Arsenical keratosis (砷中毒角化症)", ("Arsenical keratosis", "砷中毒角化症", "arsenic"), "慢性砷暴露造成掌蹠角化與皮膚癌風險增加。"),
    TopicSeed("condition", "keratoacanthoma", "Keratoacanthoma (角化棘皮瘤)", ("Keratoacanthoma", "角化棘皮瘤", "crateriform"), "快速增長的 crateriform keratinizing tumor，臨床與 SCC 可相似。"),
    TopicSeed("condition", "melanoma", "Melanoma (黑色素瘤)", ("Melanoma", "黑色素細胞瘤", "黑色素瘤", "Breslow", "ABCDE"), "惡性黑色素細胞腫瘤，預後與 Breslow thickness、潰瘍、分期等相關。"),
    TopicSeed("condition", "basal-cell-carcinoma", "Basal cell carcinoma, BCC (基底細胞癌)", ("Basal cell carcinoma", "BCC", "基底細胞癌", "pearly papule"), "最常見皮膚癌，局部侵犯為主，典型可見 pearly papule 與 telangiectasia。"),
    TopicSeed("condition", "squamous-cell-carcinoma-skin", "Cutaneous squamous cell carcinoma, cSCC (皮膚鱗狀細胞癌)", ("Squamous cell carcinoma", "SCC", "鱗狀上皮細胞癌", "cutaneous SCC"), "角質細胞惡性腫瘤，與 UV、免疫抑制、慢性傷口與前驅病變相關。"),
    TopicSeed("condition", "bowen-disease", "Bowen disease (波文氏症)", ("Bowen", "波文", "squamous cell carcinoma in situ"), "皮膚 squamous cell carcinoma in situ，表現界線清楚紅色鱗屑斑塊。"),
    TopicSeed("condition", "mycosis-fungoides", "Mycosis fungoides (蕈狀肉芽腫)", ("Mycosis fungoides", "蕈狀肉芽腫", "cutaneous T-cell lymphoma"), "最常見 cutaneous T-cell lymphoma，早期可似 eczema 或 psoriasis。"),
    # Congenital and genodermatoses.
    TopicSeed("condition", "peutz-jeghers-syndrome", "Peutz-Jeghers syndrome, PJS (Peutz-Jeghers 症候群)", ("Peutz-Jeghers", "PJS", "mucocutaneous pigmentation", "hamartomatous polyps"), "STK11 相關 hamartomatous polyposis syndrome，具口唇黏膜色素斑與腫瘤風險。"),
    TopicSeed("condition", "ichthyosis-vulgaris", "Ichthyosis vulgaris (尋常性魚鱗癬)", ("Ichthyosis vulgaris", "尋常性魚鱗癬", "filaggrin"), "常見遺傳性角化異常，表現乾燥魚鱗狀脫屑，與 filaggrin 缺陷和 atopy 相關。"),
    TopicSeed("condition", "darier-disease", "Darier disease (Darier 病)", ("Darier", "Darier's disease", "ATP2A2", "keratotic papules"), "ATP2A2 相關角化異常，表現油膩性角化丘疹、甲變化與棘融解。"),
)


SEVENTH_BOOK_SEEDS: tuple[TopicSeed, ...] = (
    # Psychiatry: psychotic and mood disorders.
    TopicSeed("condition", "schizophrenia", "Schizophrenia (思覺失調症)", ("Bleuler", "first rank symptoms", "T.J. Crow", "positive symptoms", "negative symptoms", "思覺失調症的治療", "精神分裂症的診斷"), "慢性 psychotic disorder，核心包含妄想、幻覺、語言或行為混亂、負性症狀與功能退化。"),
    TopicSeed("condition", "schizoaffective-disorder", "Schizoaffective disorder (情感性思覺失調症)", ("Schizoaffective", "情感性思覺失調"), "同時具有 psychotic symptoms 與 mood episode，且需有一段無情緒症狀的精神病症狀期。"),
    TopicSeed("condition", "schizophreniform-disorder", "Schizophreniform disorder (類思覺失調症)", ("Schizophreniform", "類思覺失調"), "症狀類似 schizophrenia，但病程介於 1 至 6 個月。"),
    TopicSeed("condition", "brief-psychotic-disorder", "Brief psychotic disorder (短暫精神病性疾患)", ("Brief psychotic", "短暫精神病"), "急性短期 psychosis，症狀至少 1 天但少於 1 個月，之後回到原功能。"),
    TopicSeed("condition", "delusional-disorder", "Delusional disorder (妄想症)", ("Delusional Disorder", "妄想症", "妄想疾患"), "以固定妄想為核心，其他功能相對保留且缺乏典型 schizophrenia 的廣泛混亂表現。"),
    TopicSeed("condition", "major-depressive-disorder", "Major depressive disorder, MDD (重度憂鬱症)", ("Major Depressive Disorder", "MDD", "重度憂鬱", "重鬱症", "major depressive episode"), "以持續低落情緒、失去興趣、睡眠食慾能量與認知改變等 depressive episode 為核心。"),
    TopicSeed("condition", "bipolar-disorder", "Bipolar disorder (躁鬱症／雙相情緒障礙)", ("Bipolar Disorder", "躁鬱症", "雙相", "bipolar"), "以躁症、輕躁症與憂鬱 episode 的組合定義，治療需避免單用 antidepressant 誘發躁化。"),
    TopicSeed("condition", "bipolar-i-disorder", "Bipolar I disorder (第一型躁鬱症)", ("Bipolar I", "第一型躁鬱", "manic episode", "躁症發作"), "至少一次 manic episode，可伴隨重鬱發作、混合特徵或 psychosis。"),
    TopicSeed("condition", "bipolar-ii-disorder", "Bipolar II disorder (第二型躁鬱症)", ("Bipolar II", "第二型躁鬱", "hypomanic episode", "輕躁發作"), "至少一次 hypomanic episode 加重鬱發作，無完整 manic episode。"),
    TopicSeed("condition", "persistent-depressive-disorder", "Persistent depressive disorder / dysthymia (持續性憂鬱症／輕鬱症)", ("Dysthymic", "Dysthymia", "輕鬱症", "persistent depressive disorder", "持續性憂鬱"), "慢性低落情緒疾病，症狀較 MDD 輕但病程長，可與 major depressive episode 疊加。"),
    TopicSeed("condition", "double-depression", "Double depression (雙鬱症)", ("Double Depression", "雙鬱症"), "persistent depressive disorder 基礎上疊加 major depressive episode。"),
    # Anxiety, OCD, trauma-related, somatic, eating, sleep, and personality disorders.
    TopicSeed("condition", "panic-disorder", "Panic disorder (恐慌症)", ("Panic Disorder", "恐慌症", "恐慌發作", "panic attack"), "反覆非預期 panic attacks，並因擔心再發作或行為改變造成明顯功能影響。"),
    TopicSeed("condition", "agoraphobia", "Agoraphobia (懼曠症／特定場所畏懼症)", ("Agoraphobia", "懼曠", "特定場所畏懼"), "害怕難以逃離或求助的場所或情境，常與 panic disorder 共病但可獨立診斷。"),
    TopicSeed("condition", "obsessive-compulsive-disorder", "Obsessive-compulsive disorder, OCD (強迫症)", ("Obsessive-Compulsive", "OCD", "強迫症", "obsession", "compulsion", "強迫思考", "強迫行為"), "反覆侵入性強迫思考與重複強迫行為，耗時或造成痛苦與功能受損。"),
    TopicSeed("condition", "specific-phobia", "Specific phobia (特定對象畏懼症)", ("Specific phobia", "特定對象畏懼", "畏懼症"), "對特定物件或情境產生過度恐懼與逃避，暴露時快速引發焦慮。"),
    TopicSeed("condition", "social-anxiety-disorder", "Social anxiety disorder / social phobia (社交焦慮症／社交畏懼症)", ("Social phobia", "Social anxiety", "社交畏懼", "社交焦慮"), "害怕社交或表現情境中被檢視、羞辱或負面評價，因而逃避或忍受強烈焦慮。"),
    TopicSeed("condition", "generalized-anxiety-disorder", "Generalized anxiety disorder, GAD (廣泛性焦慮症)", ("Generalized Anxiety Disorder", "GAD", "廣泛性焦慮"), "長期過度擔心多種事件，伴隨肌肉緊繃、易疲倦、注意力差、睡眠與自律神經症狀。"),
    TopicSeed("condition", "posttraumatic-stress-disorder", "Posttraumatic stress disorder, PTSD (創傷後壓力症候群)", ("Posttraumatic Stress Disorder", "PTSD", "創傷後壓力"), "創傷暴露後出現侵入、逃避、負向認知情緒與警覺性升高等症狀群。"),
    TopicSeed("condition", "somatic-symptom-disorder", "Somatic symptom disorder (身體症狀障礙／身體化疾患)", ("Somatization Disorder", "Somatic symptom", "身體化疾患", "身體症狀障礙"), "多重身體症狀與過度健康焦慮或醫療尋求，需排除可解釋的內外科病因。"),
    TopicSeed("condition", "conversion-disorder", "Conversion disorder / functional neurological symptom disorder (轉化症)", ("Conversion Disorder", "轉化症", "functional neurological"), "心理壓力或衝突轉化為神經症狀，如癱瘓、失明或 seizure-like episodes，症狀與神經解剖不完全相符。"),
    TopicSeed("condition", "illness-anxiety-disorder", "Illness anxiety disorder / hypochondriasis (慮病症)", ("Hypochondriasis", "Illness anxiety", "慮病症"), "對罹患重大疾病的焦慮持續存在，即使檢查陰性仍難以安心。"),
    TopicSeed("condition", "anorexia-nervosa", "Anorexia nervosa (神經性厭食症)", ("Anorexia Nervosa", "神經性厭食", "body weight", "fear of gaining weight"), "限制攝食導致低體重、強烈害怕變胖與身體意象扭曲，可伴隨 purging 或過度運動。"),
    TopicSeed("condition", "sleep-disorders", "Sleep disorders (睡眠疾患)", ("睡眠疾患", "睡眠型態", "insomnia", "parasomnia", "REM sleep", "NREM"), "睡眠量、品質、時序或睡眠中行為異常的疾病群，需區分精神、藥物與身體病因。"),
    TopicSeed("condition", "personality-disorders", "Personality disorders (人格疾患)", ("人格違常", "Personality disorder", "A 群人格", "B 群人格", "C 群人格"), "持久且僵化的內在經驗與行為模式偏離文化期待，造成痛苦或功能受損。"),
    TopicSeed("condition", "gender-dysphoria", "Gender dysphoria (性別不安／性別認同困擾)", ("Gender dysphoria", "性別認同", "性別不安"), "性別認同與出生指定性別不一致造成顯著痛苦或功能受損。"),
    # Substance-related disorders.
    TopicSeed("condition", "substance-use-disorder", "Substance use disorder (物質使用疾患)", ("Substance use disorder", "物質使用疾患", "物質依賴", "物質濫用"), "以失控使用、耐受、戒斷、渴求與角色功能受損等模式定義的成癮疾病群。"),
    TopicSeed("condition", "alcohol-use-disorder", "Alcohol use disorder (酒精使用疾患)", ("Alcohol use disorder", "酒精使用疾患", "酒精依賴", "酒精濫用"), "酒精相關失控使用與功能損害，常與 mood、anxiety、肝病與事故風險相關。"),
    TopicSeed("condition", "alcohol-intoxication", "Alcohol intoxication (酒精中毒)", ("酒精中毒", "Alcohol intoxication", "blood alcohol concentration"), "急性酒精攝入造成行為、協調、言語、意識與生命徵象變化。"),
    TopicSeed("condition", "alcohol-withdrawal-syndrome", "Alcohol withdrawal syndrome (酒精戒斷症候群)", ("Alcohol withdrawal", "酒精戒斷", "delirium tremens", "withdrawal seizure"), "長期大量飲酒後減量或停用造成自律神經亢進、顫抖、癲癇或譫妄。"),
    TopicSeed("condition", "wernicke-korsakoff-syndrome", "Wernicke-Korsakoff syndrome (韋尼克-科薩科夫症候群)", ("Wernicke", "Korsakoff", "Alcohol-induced persisting amnestic", "永久失憶疾患", "thiamine"), "thiamine deficiency 相關腦病變與持續失憶，常見於 alcohol use disorder。"),
    TopicSeed("condition", "amphetamine-intoxication", "Amphetamine intoxication (安非他命中毒)", ("Amphetamine intoxication", "安非他命中毒", "stimulant intoxication"), "stimulant 過量造成交感亢進、瞳孔放大、激動、失眠、妄想或幻覺。"),
    TopicSeed("condition", "amphetamine-withdrawal", "Amphetamine withdrawal (安非他命戒斷)", ("Amphetamine withdrawal", "安非他命戒斷"), "stimulant 停用後可出現疲倦、嗜睡、憂鬱、食慾增加與強烈渴求。"),
    TopicSeed("condition", "amphetamine-induced-psychotic-disorder", "Amphetamine-induced psychotic disorder (安非他命引起的精神病性疾患)", ("Amphetamine-induced psychotic", "安非他命引起的精神"), "stimulant 使用後出現妄想、幻覺或激動，臨床需與 schizophrenia、mania 與 delirium 鑑別。"),
    TopicSeed("condition", "opioid-intoxication", "Opioid intoxication (鴉片類中毒)", ("Opioid intoxication", "鴉片中毒", "miosis", "respiratory depression"), "opioid 過量典型為意識下降、呼吸抑制與針尖瞳孔，屬高風險急症。"),
    TopicSeed("condition", "opioid-withdrawal", "Opioid withdrawal (鴉片類戒斷)", ("Opioid withdrawal", "鴉片戒斷", "lacrimation", "rhinorrhea", "piloerection"), "opioid 停用後出現流淚流鼻水、雞皮疙瘩、腹瀉、肌痛、焦躁與失眠。"),
    TopicSeed("condition", "ketamine-use-disorder", "Ketamine-related disorder (K 他命相關疾患)", ("Ketamine", "K 他命", "ketamine-related"), "ketamine 使用可造成解離、認知影響、泌尿道症狀與成癮相關問題。"),
    TopicSeed("condition", "mdma-use-disorder", "MDMA-related disorder (MDMA／搖頭丸相關疾患)", ("MDMA", "搖頭丸", "ecstasy"), "MDMA 使用與 serotonin、交感亢進、體溫調節異常和精神症狀相關。"),
    # Geriatric, child/adolescent, suicide.
    TopicSeed("condition", "dementia", "Dementia / major neurocognitive disorder (失智症)", ("失智症 (Dementia)", "Dementia 與假性失智症", "major neurocognitive", "alcohol-induced persisting dementia", "失智症/譫妄"), "後天認知功能下降影響日常生活，需區分退化性、血管性、代謝、藥物、憂鬱與譫妄。"),
    TopicSeed("condition", "alzheimer-disease", "Alzheimer disease (阿茲海默氏病)", ("Alzheimer", "阿茲海默", "amyloid", "tau"), "最常見失智症原因，與 amyloid plaques、tau tangles、海馬萎縮與進行性記憶退化相關。"),
    TopicSeed("condition", "vascular-dementia", "Vascular dementia (血管性失智症)", ("Vascular dementia", "血管性失智", "multi-infarct"), "腦血管病變造成階梯式或執行功能為主的認知下降，可與中風危險因子相關。"),
    TopicSeed("condition", "pseudodementia", "Pseudodementia (假性失智症)", ("Pseudodementia", "假性失智"), "憂鬱等可逆精神狀態造成類似失智的認知表現，需與 degenerative dementia 鑑別。"),
    TopicSeed("condition", "delirium", "Delirium (譫妄)", ("Delirium", "譫妄", "attention disturbance", "意識障礙"), "急性波動性注意力與意識障礙，常由感染、藥物、代謝或住院壓力誘發。"),
    TopicSeed("condition", "autism-spectrum-disorder", "Autism spectrum disorder, ASD (自閉症類群障礙)", ("Autistic Disorder", "Autism", "ASD", "自閉性疾患", "自閉症"), "神經發展疾病，核心為社會溝通互動缺損與侷限重複行為或興趣。"),
    TopicSeed("condition", "tic-disorder", "Tic disorder (抽動疾患)", ("Tic Disorder", "抽動疾患", "tic disorder"), "突然、快速、反覆、非節律性的動作或聲語 tic；需依型態與持續時間分類。"),
    TopicSeed("condition", "intellectual-disability", "Intellectual disability (智能不足／智能障礙)", ("Mental Retardation", "Intellectual disability", "智能不足", "智能障礙"), "智力與適應功能在發展期即低於預期，嚴重度以日常支持需求與適應功能評估。"),
    TopicSeed("condition", "suicidal-behavior", "Suicidal behavior (自殺行為)", ("Suicide", "自殺", "suicidal behavior", "suicidal ideation", "自殺行為"), "包含自殺意念、計畫、企圖與完成自殺，需評估危險因子、保護因子與急迫性。"),
    TopicSeed("condition", "nonsuicidal-self-injury", "Nonsuicidal self-injury, NSSI (非自殺性自傷)", ("Nonsuicidal", "self-injury", "自傷", "NSSI"), "無意圖死亡的自我傷害行為，仍需評估自殺風險、情緒調節與共病。"),
    # Psychiatry diagnostics, concepts, drugs, and procedures.
    TopicSeed("diagnostic", "dsm-diagnostic-criteria", "DSM diagnostic criteria (DSM 診斷準則)", ("DSM-IV-TR", "DSM-5", "DSM 診斷", "診斷準則"), "精神科疾病分類與診斷準則框架；教材同時使用 DSM-IV-TR 與 DSM-5，需注意版本差異。"),
    TopicSeed("diagnostic", "mental-status-examination", "Mental status examination, MSE (精神狀態檢查)", ("Mental status", "MSE", "精神狀態", "意識", "情緒", "思考"), "精神科會談中系統評估外觀、行為、語言、情緒、思考、知覺、認知、病識感與判斷力。"),
    TopicSeed("diagnostic", "suicide-risk-assessment", "Suicide risk assessment (自殺風險評估)", ("自殺危險因子", "suicide risk", "自殺風險", "自殺評估"), "評估自殺意念、計畫、手段可近性、過去企圖、精神疾患、物質使用、保護因子與支持系統。"),
    TopicSeed("diagnostic", "mini-mental-state-examination", "Mini-Mental State Examination, MMSE (簡易智能狀態檢查)", ("MMSE", "Mini-Mental", "簡易智能"), "常用認知篩檢工具，可協助失智症與譫妄評估但受教育與語言影響。"),
    TopicSeed("concept", "psychosis", "Psychosis (精神病性症狀)", ("psychosis", "psychotic", "精神病", "妄想", "幻覺"), "現實感受損的症狀群，包含妄想、幻覺、思考形式障礙與混亂行為。"),
    TopicSeed("concept", "monoamine-hypothesis", "Monoamine hypothesis (單胺假說)", ("monoamine", "serotonin", "norepinephrine", "dopamine", "單胺"), "以 serotonin、norepinephrine、dopamine 等 neurotransmitters 解釋 mood、psychosis 與藥物機轉的概念。"),
    TopicSeed("drug", "antipsychotics", "Antipsychotics (抗精神病藥物)", ("Antipsychotics", "抗精神病藥物", "D2 receptor", "dopamine receptor", "Haloperidol", "Risperidone", "Olanzapine"), "主要用於 psychosis、mania 與部分行為激動；需監測 EPS、metabolic syndrome、QT prolongation、NMS 等。"),
    TopicSeed("condition", "extrapyramidal-symptoms", "Extrapyramidal symptoms, EPS (錐體外症狀)", ("Extrapyramidal", "EPS", "錐體外症狀", "akathisia", "dystonia", "parkinsonism"), "多巴胺阻斷相關動作副作用，包含急性肌張力不全、靜坐不能、類巴金森症與遲發性不自主運動。"),
    TopicSeed("condition", "neuroleptic-malignant-syndrome", "Neuroleptic malignant syndrome, NMS (抗精神病藥物惡性症候群)", ("Neuroleptic malignant syndrome", "NMS", "抗精神病藥物惡性症候群"), "dopamine blockade 相關高熱、肌肉僵硬、自律神經不穩與 CK 升高的高風險藥物反應。"),
    TopicSeed("drug", "antidepressants", "Antidepressants (抗憂鬱藥物)", ("Antidepressants", "抗憂鬱", "抗憂鬱劑", "TCA", "SSRI", "SNRI", "MAOI"), "治療 depression、anxiety、OCD、PTSD 等；選擇需考慮副作用、交互作用、自殺風險與 bipolar screening。"),
    TopicSeed("drug", "selective-serotonin-reuptake-inhibitors", "Selective serotonin reuptake inhibitors, SSRIs (選擇性血清素回收抑制劑)", ("SSRI", "SSRIs", "fluoxetine", "sertraline", "paroxetine", "選擇性血清素"), "常用 antidepressant/anxiolytic 類別，需注意 GI、sexual dysfunction、serotonin syndrome 與初期焦慮。"),
    TopicSeed("drug", "tricyclic-antidepressants", "Tricyclic antidepressants, TCAs (三環抗憂鬱劑)", ("TCA", "tricyclic", "Imipramine", "Amitriptyline", "三環"), "傳統抗憂鬱藥，具 anticholinergic、cardiotoxicity 與 overdose 風險。"),
    TopicSeed("drug", "monoamine-oxidase-inhibitors", "Monoamine oxidase inhibitors, MAOIs (單胺氧化酶抑制劑)", ("MAOI", "monoamine oxidase", "單胺氧化"), "抗憂鬱藥類，需注意 tyramine diet、hypertensive crisis 與藥物交互作用。"),
    TopicSeed("drug", "benzodiazepines", "Benzodiazepines, BZD (苯二氮平類)", ("Benzodiazepine", "BZD", "benzodiazepines", "Lorazepam", "Diazepam", "Alprazolam", "苯二氮"), "增強 GABA-A 作用，用於 anxiety、insomnia、alcohol withdrawal、seizure 與急性激動；需注意依賴、跌倒與呼吸抑制。"),
    TopicSeed("drug", "lithium", "Lithium (鋰鹽)", ("Lithium", "鋰鹽", "lithium toxicity"), "mood stabilizer，用於 bipolar disorder 與自殺風險降低；需監測血中濃度、腎功能、甲狀腺與交互作用。"),
    TopicSeed("drug", "valproate", "Valproate / valproic acid (丙戊酸)", ("Valproate", "Valproic", "丙戊酸", "Depakine"), "mood stabilizer 與抗癲癇藥，用於 mania；需注意肝毒性、血小板、胰臟炎、體重與致畸胎性。"),
    TopicSeed("drug", "carbamazepine", "Carbamazepine (卡馬西平)", ("Carbamazepine", "卡馬西平", "Tegretol"), "抗癲癇與 mood stabilizer，可用於 mania；需注意皮疹、SJS/TEN、hyponatremia、血球低下與 CYP 交互作用。"),
    TopicSeed("drug", "methylphenidate", "Methylphenidate (哌甲酯)", ("Methylphenidate", "Ritalin", "哌甲酯", "利他能"), "中樞神經刺激劑，用於 ADHD；需注意食慾、睡眠、血壓心跳與物質濫用風險。"),
    TopicSeed("procedure", "electroconvulsive-therapy", "Electroconvulsive therapy, ECT (電痙攣治療)", ("Electroconvulsive", "ECT", "電痙攣"), "以麻醉下誘發治療性癲癇發作用於重度憂鬱、mania、catatonia、部分 psychosis 或緊急自殺風險。"),
    TopicSeed("procedure", "psychotherapy", "Psychotherapy (心理治療)", ("psychotherapy", "心理治療", "支持性心理治療", "心理社會治療"), "透過治療關係、認知行為、支持與人際介入改善症狀、功能與復健。"),
    TopicSeed("procedure", "cognitive-behavioral-therapy", "Cognitive behavioral therapy, CBT (認知行為治療)", ("CBT", "cognitive behavioral", "認知行為"), "針對自動化思考、行為逃避與暴露反應預防等機制的結構化心理治療。"),
)


EIGHTH_BOOK_SEEDS: tuple[TopicSeed, ...] = (
    # Neurology: exam, anatomy, localization, and diagnostics.
    TopicSeed("anatomy", "central-nervous-system", "Central nervous system, CNS (中樞神經系統)", ("central nervous system", "CNS", "中樞神經", "腦部", "脊髓"), "包含 brain 與 spinal cord，是神經定位、感染、血管、退化與脫髓鞘疾病的核心架構。"),
    TopicSeed("anatomy", "cranial-nerves", "Cranial nerves (腦神經)", ("cranial nerve", "腦神經", "CN III", "CN VI", "顱神經"), "十二對腦神經連結眼球運動、臉部感覺運動、聽平衡、吞嚥與自律神經功能。"),
    TopicSeed("anatomy", "basal-ganglia", "Basal ganglia (基底核)", ("basal ganglia", "基底核", "substantia nigra", "direct pathway", "indirect pathway"), "調節動作起始、抑制與不自主運動；Parkinson disease、Huntington disease、Wilson disease 常涉及此迴路。"),
    TopicSeed("anatomy", "cerebellum", "Cerebellum (小腦)", ("cerebellum", "小腦", "ataxia", "dysmetria"), "負責協調、平衡與動作修正，小腦病灶常表現 ataxia、dysmetria、nystagmus。"),
    TopicSeed("anatomy", "brainstem", "Brainstem (腦幹)", ("brainstem", "腦幹", "midbrain", "pons", "medulla"), "中腦、橋腦、延腦含腦神經核、長徑路與生命中樞，病灶可造成交叉性神經缺損。"),
    TopicSeed("anatomy", "spinal-cord", "Spinal cord (脊髓)", ("spinal cord", "脊髓", "anterior cord", "posterior column", "lateral corticospinal"), "傳遞運動、感覺與自律訊號；病灶定位依節段、長徑路與上下運動神經元表現。"),
    TopicSeed("anatomy", "peripheral-nerves", "Peripheral nerves (周邊神經)", ("peripheral nerve", "周邊神經", "polyneuropathy", "mononeuropathy"), "周邊神經包含 motor、sensory 與 autonomic fibers，疾病常依軸突、髓鞘、單神經或多發神經分類。"),
    TopicSeed("anatomy", "neuromuscular-junction", "Neuromuscular junction, NMJ (神經肌肉接合處)", ("neuromuscular junction", "NMJ", "神經肌肉接合", "acetylcholine receptor"), "motor neuron 與 skeletal muscle 之間以 acetylcholine 傳遞訊號，是 MG、Lambert-Eaton、botulism 的病變位置。"),
    TopicSeed("physiology", "corticospinal-tract", "Corticospinal tract (皮質脊髓徑)", ("corticospinal tract", "皮質脊髓徑", "pyramidal tract", "錐體束"), "主要 voluntary motor pathway，病灶造成上運動神經元徵象與定位價值。"),
    TopicSeed("concept", "upper-motor-neuron-lesion", "Upper motor neuron lesion, UMN lesion (上運動神經元病灶)", ("upper motor neuron", "UMN", "上運動神經元", "spasticity", "Babinski"), "UMN lesion 常見 weakness、spasticity、hyperreflexia、Babinski sign。"),
    TopicSeed("concept", "lower-motor-neuron-lesion", "Lower motor neuron lesion, LMN lesion (下運動神經元病灶)", ("lower motor neuron", "LMN", "下運動神經元", "fasciculation", "atrophy"), "LMN lesion 常見 weakness、atrophy、fasciculation、hyporeflexia。"),
    TopicSeed("diagnostic", "neurologic-examination", "Neurologic examination (神經學檢查)", ("神經學檢查", "neurologic examination", "neurological examination"), "系統評估 mental status、cranial nerves、motor、sensory、reflex、coordination、gait 以定位神經病灶。"),
    TopicSeed("diagnostic", "glasgow-coma-scale", "Glasgow Coma Scale, GCS (格拉斯哥昏迷指數)", ("Glasgow", "GCS", "格拉斯哥"), "以 eye、verbal、motor response 評估意識程度，常用於腦傷、中風與急症神經評估。"),
    TopicSeed("diagnostic", "electroencephalography", "Electroencephalography, EEG (腦電圖)", ("EEG", "electroencephalography", "腦電波", "腦電圖"), "記錄大腦皮質電活動，用於 epilepsy 分型、encephalopathy、CNS infection 與 CJD 等評估。"),
    TopicSeed("diagnostic", "nerve-conduction-study", "Nerve conduction study, NCS/NCV (神經傳導檢查)", ("nerve conduction", "NCV", "NCS", "神經傳導"), "評估周邊神經傳導速度與振幅，協助區分 axonal neuropathy 與 demyelinating neuropathy。"),
    TopicSeed("diagnostic", "electromyography", "Electromyography, EMG (肌電圖)", ("EMG", "electromyography", "肌電圖", "needle EMG"), "針極肌電圖評估肌肉與下運動神經元電活動，用於 motor neuron disease、radiculopathy、myopathy 等。"),
    TopicSeed("diagnostic", "evoked-potential-test", "Evoked potential test (誘發電位檢查)", ("evoked potential", "誘發電位", "VEP", "SSEP"), "以視覺、聽覺或體感刺激測量傳導路徑反應，常用於 demyelinating disease 評估。"),
    TopicSeed("diagnostic", "brain-computed-tomography", "Brain computed tomography, brain CT (腦部電腦斷層)", ("brain CT", "腦部 CT", "電腦斷層", "non-contrast CT"), "急性神經症狀常用初始影像，特別用於排除出血、腦水腫、腫塊效應。"),
    TopicSeed("diagnostic", "brain-magnetic-resonance-imaging", "Brain magnetic resonance imaging, brain MRI (腦部磁振造影)", ("brain MRI", "腦部 MRI", "magnetic resonance", "DWI", "FLAIR"), "對急性缺血、脫髓鞘、腫瘤、感染與後顱窩病灶較敏感。"),
    TopicSeed("procedure", "lumbar-puncture", "Lumbar puncture, LP (腰椎穿刺)", ("lumbar puncture", "腰椎穿刺", "spinal tap", "LP"), "取得 cerebrospinal fluid 以診斷 CNS infection、subarachnoid hemorrhage、demyelinating disease 等；IICP 或 mass effect 時需先評估風險。"),
    # Epilepsy and antiseizure drugs.
    TopicSeed("condition", "epilepsy", "Epilepsy (癲癇)", ("epileptic seizure", "癲癇發作(seizure)", "癲癇 (epilepsy)", "抗癲癇藥物", "Anti-Epileptic Drug"), "反覆非誘發性 seizure 或具再發風險的疾病，需依發作型態、EEG 與病因分類。"),
    TopicSeed("condition", "focal-seizure", "Focal seizure (局部性癲癇發作)", ("focal seizure", "partial seizure", "局部性發作", "simple partial", "complex partial"), "起源於單側局部皮質，可保留或影響意識，症狀反映病灶位置。"),
    TopicSeed("condition", "generalized-tonic-clonic-seizure", "Generalized tonic-clonic seizure, GTCS (全身強直陣攣發作)", ("generalized tonic-clonic", "GTCS", "強直陣攣", "grand mal"), "雙側皮質網路造成意識喪失、強直期與陣攣期，發作後常有 postictal confusion。"),
    TopicSeed("condition", "absence-seizure", "Absence seizure (失神發作)", ("absence seizure", "失神發作", "petit mal", "3-Hz spike"), "短暫意識中斷與 staring，典型 EEG 為 3-Hz spike-and-wave。"),
    TopicSeed("condition", "status-epilepticus", "Status epilepticus (癲癇重積狀態)", ("status epilepticus", "癲癇重積", "持續發作"), "持續或反覆 seizure 未恢復基準意識，需即時 benzodiazepine 與後續 antiseizure therapy。"),
    TopicSeed("drug", "anti-seizure-medications", "Anti-seizure medications / anti-epileptic drugs, ASMs/AEDs (抗癲癇藥物)", ("Anti-Epileptic Drug", "AED", "anti-seizure", "抗癲癇藥物"), "治療 epilepsy 與急性 seizure 的藥物群，選擇依發作型態、副作用、懷孕與共病。"),
    TopicSeed("drug", "phenytoin", "Phenytoin (苯妥英)", ("Phenytoin", "苯妥英", "Dilantin"), "Na channel blocker 類 antiseizure medication，可用於 focal seizure、GTCS 與 status epilepticus 後續控制。"),
    TopicSeed("drug", "ethosuximide", "Ethosuximide (乙琥胺)", ("Ethosuximide", "乙琥胺", "T-type calcium"), "T-type calcium channel blocker，是典型 absence seizure 常用藥。"),
    TopicSeed("drug", "lamotrigine", "Lamotrigine (拉莫三嗪)", ("Lamotrigine", "拉莫三嗪", "Lamictal"), "Na channel blocker 類 antiseizure/mood stabilizer，需注意皮疹與 SJS/TEN 風險。"),
    TopicSeed("drug", "levetiracetam", "Levetiracetam (左乙拉西坦)", ("Levetiracetam", "左乙拉西坦", "Keppra"), "常用 broad-spectrum antiseizure medication，交互作用較少但可有情緒行為副作用。"),
    TopicSeed("drug", "topiramate", "Topiramate (托吡酯)", ("Topiramate", "托吡酯", "Topamax"), "多機轉 antiseizure medication，也可用於 migraine prophylaxis；需注意認知、體重、腎結石。"),
    TopicSeed("drug", "phenobarbital", "Phenobarbital (苯巴比妥)", ("Phenobarbital", "苯巴比妥", "barbiturate"), "barbiturate 類 antiseizure medication，加強 GABA 作用，具鎮靜與呼吸抑制風險。"),
    # Headache.
    TopicSeed("condition", "headache", "Headache (頭痛)", ("頭痛", "headache", "primary headache", "secondary headache"), "頭痛需先分辨 primary headache 與 secondary red flags，如 CNS infection、SAH、IICP、tumor、temporal arteritis。"),
    TopicSeed("condition", "migraine", "Migraine (偏頭痛)", ("Migraine", "偏頭痛", "aura", "photophobia", "phonophobia"), "反覆中重度搏動性頭痛，可伴隨噁心、畏光畏聲與 aura。"),
    TopicSeed("condition", "tension-type-headache", "Tension-type headache (緊縮型頭痛)", ("Tension headache", "tension-type", "緊縮型頭痛"), "常見 primary headache，呈雙側壓迫緊箍感，通常無明顯噁心或神經缺損。"),
    TopicSeed("condition", "cluster-headache", "Cluster headache (叢發型頭痛)", ("Cluster headache", "叢發型頭痛", "trigeminal autonomic"), "三叉自律神經頭痛，典型為單側眼眶顳部劇痛合併流淚、鼻塞或 Horner-like signs。"),
    TopicSeed("condition", "raised-intracranial-pressure", "Raised intracranial pressure, IICP (顱內壓升高)", ("IICP", "顱內壓", "intracranial pressure", "papilledema"), "顱內壓升高可造成頭痛、嘔吐、視乳頭水腫與意識變化，腰椎穿刺前需評估。"),
    TopicSeed("condition", "intracranial-hypotension", "Intracranial hypotension (顱內壓低下)", ("intracranial hypotension", "顱內壓太低", "腰椎穿刺後", "post-lumbar puncture headache"), "CSF leak 或 lumbar puncture 後可造成姿勢性頭痛，平躺改善。"),
    TopicSeed("drug", "triptans", "Triptans (翠普登類)", ("Triptan", "triptans", "Sumatriptan", "翠普登"), "5-HT1B/1D agonists，用於 acute migraine/cluster headache，但血管疾病風險者需小心。"),
    TopicSeed("drug", "ergot-alkaloids", "Ergot alkaloids (麥角生物鹼)", ("Ergotamine", "ergot", "麥角"), "用於 migraine 急性治療的血管收縮藥物，副作用與禁忌較多。"),
    # Stroke and vascular neurology.
    TopicSeed("condition", "stroke", "Stroke / cerebrovascular accident, CVA (腦中風)", ("Stroke", "CVA", "腦中風", "cerebrovascular disease", "腦血管疾病"), "腦血管阻塞或破裂造成急性局部神經功能缺損，需快速分辨 ischemic 與 hemorrhagic stroke。"),
    TopicSeed("condition", "ischemic-stroke", "Ischemic stroke (缺血性腦中風)", ("Ischemic Stroke", "缺血性腦中風", "腦梗塞", "cerebral infarction"), "腦血流中斷造成 infarction，常依 TOAST 病因、血管位置與時間窗決定治療。"),
    TopicSeed("condition", "transient-ischemic-attack", "Transient ischemic attack, TIA (暫時性腦缺血發作)", ("TIA", "transient ischemic", "暫時性腦缺血"), "短暫局部神經缺損且無急性 infarction，提示後續 stroke 風險。"),
    TopicSeed("condition", "lacunar-infarction", "Lacunar infarction (腔隙性腦梗塞)", ("Lacunar infarction", "腔隙性腦梗塞", "small vessel"), "小穿通動脈閉塞造成深部小梗塞，常與高血壓、糖尿病相關。"),
    TopicSeed("condition", "intracerebral-hemorrhage", "Intracerebral hemorrhage, ICH (腦出血)", ("Intracerebral hemorrhage", "ICH", "腦出血", "putaminal hemorrhage"), "腦實質出血，常與高血壓、amyloid angiopathy、AVM、抗凝或腫瘤相關。"),
    TopicSeed("condition", "subarachnoid-hemorrhage", "Subarachnoid hemorrhage, SAH (蜘蛛膜下腔出血)", ("Subarachnoid hemorrhage", "SAH", "蜘蛛膜下腔出血", "thunderclap"), "常由 ruptured aneurysm 引起，典型 thunderclap headache，需注意再出血與 vasospasm。"),
    TopicSeed("condition", "cerebral-aneurysm", "Cerebral aneurysm (腦動脈瘤)", ("cerebral aneurysm", "腦動脈瘤", "berry aneurysm", "aneurysm"), "顱內動脈壁局部擴張，破裂可造成 SAH。"),
    TopicSeed("condition", "cerebral-arteriovenous-malformation", "Cerebral arteriovenous malformation, AVM (腦動靜脈畸形)", ("AVM", "arteriovenous malformation", "動靜脈畸形"), "動脈與靜脈異常短路，可造成出血、seizure 或局部神經缺損。"),
    TopicSeed("diagnostic", "toast-stroke-classification", "TOAST stroke classification (TOAST 中風病因分類)", ("TOAST", "stroke classification", "中風病因分類"), "急性缺血性中風病因分類，包含 large artery atherosclerosis、cardioembolism、small vessel 等。"),
    TopicSeed("drug", "alteplase", "Alteplase / rtPA (組織型纖溶酶原活化劑)", ("Alteplase", "rtPA", "tPA", "組織型纖溶酶原"), "急性 ischemic stroke 血栓溶解藥物，需符合時間窗與禁忌篩選。"),
    TopicSeed("drug", "nimodipine", "Nimodipine (尼莫地平)", ("Nimodipine", "尼莫地平"), "dihydropyridine calcium channel blocker，SAH 後用於降低 delayed cerebral ischemia 風險。"),
    TopicSeed("procedure", "stroke-thrombolysis", "Stroke thrombolysis (中風血栓溶解治療)", ("thrombolysis", "血栓溶解", "rtPA", "tPA"), "急性 ischemic stroke 在合適時間窗與條件下以 alteplase 等進行再灌流治療。"),
    TopicSeed("procedure", "mechanical-thrombectomy", "Mechanical thrombectomy (機械取栓)", ("mechanical thrombectomy", "機械取栓", "endovascular thrombectomy"), "大血管阻塞 ischemic stroke 的血管內再灌流程序。"),
    TopicSeed("procedure", "aneurysm-clipping-coiling", "Aneurysm clipping/coiling (動脈瘤夾閉／栓塞)", ("clipping", "coiling", "動脈瘤夾", "栓塞"), "ruptured cerebral aneurysm 可用外科夾閉或血管內 coiling 降低再出血風險。"),
    # Dementia, movement disorders, and metabolic brain disease.
    TopicSeed("condition", "frontotemporal-dementia", "Frontotemporal dementia, FTD (額顳葉型失智症)", ("Frontotemporal dementia", "FTD", "額顳葉型失智"), "以行為、人格或語言變化為早期核心的退化性失智症群。"),
    TopicSeed("condition", "dementia-with-lewy-bodies", "Dementia with Lewy bodies, DLB (路易氏體失智症)", ("Dementia with Lewy", "DLB", "路易氏體失智"), "失智合併波動性認知、視幻覺、parkinsonism 與 REM sleep behavior disorder。"),
    TopicSeed("condition", "parkinson-disease", "Parkinson disease (巴金森氏病)", ("巴金森氏症 (Parkinsonism)", "Parkinsonism) 總整理", "substantia nigra", "bradykinesia", "resting tremor"), "黑質 dopaminergic neurons 退化造成 bradykinesia、resting tremor、rigidity 與姿勢不穩。"),
    TopicSeed("condition", "essential-tremor", "Essential tremor (原發性顫抖症)", ("Essential tremor", "原發性顫抖", "action tremor"), "常見動作性或姿勢性顫抖，常影響手部與頭部，與 Parkinson resting tremor 需鑑別。"),
    TopicSeed("condition", "huntington-disease", "Huntington disease (亨汀頓舞蹈症)", ("Huntington", "亨汀頓", "chorea", "CAG"), "CAG repeat expansion 造成舞蹈症、精神症狀與認知退化。"),
    TopicSeed("condition", "central-pontine-myelinolysis", "Central pontine myelinolysis / osmotic demyelination syndrome (橋腦中央髓鞘溶解症)", ("Central pontine myelinolysis", "osmotic demyelination", "橋腦中央", "hyponatremia correction"), "低血鈉快速矯正後可能發生的 pontine demyelination，造成意識與長徑路症狀。"),
    TopicSeed("condition", "subacute-combined-degeneration", "Subacute combined degeneration (亞急性合併退化症)", ("subacute combined", "亞急性合併退化", "Vitamin B12", "cobalamin"), "vitamin B12 deficiency 造成 posterior columns 與 corticospinal tracts 退化。"),
    TopicSeed("drug", "levodopa", "Levodopa (左旋多巴)", ("Levodopa", "左旋多巴", "L-dopa"), "dopamine precursor，是 Parkinson disease 對症治療核心藥物，長期可有 wearing-off 與 dyskinesia。"),
    TopicSeed("drug", "dopamine-agonists", "Dopamine agonists (多巴胺致效劑)", ("dopamine agonist", "多巴胺致效", "Pramipexole", "Ropinirole", "Bromocriptine"), "直接刺激 dopamine receptors，用於 Parkinson disease，但可有嗜睡、幻覺、衝動控制障礙。"),
    TopicSeed("drug", "mao-b-inhibitors", "MAO-B inhibitors (MAO-B 抑制劑)", ("MAO-B", "Selegiline", "Rasagiline"), "減少 dopamine 分解，可用於 Parkinson disease 症狀控制。"),
    # Demyelinating, spinal cord, peripheral nerve, NMJ, and muscle disease.
    TopicSeed("condition", "amyotrophic-lateral-sclerosis", "Amyotrophic lateral sclerosis, ALS (肌萎縮側索硬化症)", ("Amyotrophic lateral sclerosis", "ALS", "肌萎縮側索硬化"), "同時侵犯 UMN 與 LMN 的 motor neuron disease，表現進行性無力、萎縮、束顫與 spasticity。"),
    TopicSeed("condition", "multiple-sclerosis", "Multiple sclerosis, MS (多發性硬化症)", ("Multiple sclerosis", "MS", "多發性硬化", "oligoclonal band"), "CNS demyelinating disease，常有時間與空間多發性，侵犯視神經、脊髓、腦幹與白質。"),
    TopicSeed("condition", "neuromyelitis-optica", "Neuromyelitis optica, NMO (視神經脊髓炎)", ("Neuromyelitis optica", "NMO", "Devic", "視神經脊"), "AQP4-IgG 相關 astrocytopathy，典型侵犯 optic nerves 與 longitudinally extensive transverse myelitis。"),
    TopicSeed("condition", "progressive-multifocal-leukoencephalopathy", "Progressive multifocal leukoencephalopathy, PML (進行性多灶性白質腦病)", ("Progressive multifocal", "PML", "進行性多灶性白質腦病", "JC virus"), "JC virus 在免疫低下者造成 CNS demyelination，表現進行性局部神經缺損。"),
    TopicSeed("condition", "leukodystrophy", "Leukodystrophy (白質失養症)", ("Leukodystrophy", "白質失養"), "遺傳或代謝性白質疾病群，造成進行性神經退化與 demyelination。"),
    TopicSeed("condition", "acute-disseminated-encephalomyelitis", "Acute disseminated encephalomyelitis, ADEM (急性瀰散型腦脊髓炎)", ("ADEM", "Acute disseminated", "急性瀰散型腦脊髓炎"), "多為感染或疫苗後單相 CNS inflammatory demyelination，常有 encephalopathy。"),
    TopicSeed("condition", "chronic-inflammatory-demyelinating-polyneuropathy", "Chronic inflammatory demyelinating polyneuropathy, CIDP (慢性發炎性脫髓鞘型多發神經病變)", ("CIDP", "慢性發炎性", "chronic inflammatory demyelinating"), "慢性免疫性 demyelinating polyneuropathy，可有近端與遠端無力、感覺症狀與反射下降。"),
    TopicSeed("condition", "polyneuropathy", "Polyneuropathy (多發性神經病變)", ("Polyneuropathy", "多發性神經病變", "stocking-glove"), "多條周邊神經受累，常呈 distal symmetric sensory-motor pattern。"),
    TopicSeed("condition", "cranial-nerve-palsy", "Cranial nerve palsy (腦神經麻痺)", ("cranial nerve palsy", "顱神經麻痺", "腦神經麻痺"), "腦神經功能受損造成眼動、臉部、吞嚥、聽平衡等症狀，需定位核、束、神經或肌肉。"),
    TopicSeed("condition", "lambert-eaton-myasthenic-syndrome", "Lambert-Eaton myasthenic syndrome, LEMS (Lambert-Eaton 肌無力症候群)", ("Lambert-Eaton", "LEMS", "Lambert-Eaton syndrome"), "presynaptic voltage-gated calcium channel antibody 疾病，常與 small-cell lung cancer 相關，重複收縮後力量改善。"),
    TopicSeed("condition", "muscular-dystrophy", "Muscular dystrophy (肌肉失養症)", ("Muscular dystrophy", "肌肉失養症", "dystrophin"), "遺傳性肌肉結構蛋白疾病群，造成進行性肌無力與肌肉退化。"),
    TopicSeed("condition", "hypokalemic-periodic-paralysis", "Hypokalemic periodic paralysis (低血鉀週期性麻痺)", ("Hypokalemia Periodic Paralysis", "低血鉀週期性", "週期性肌無力"), "低血鉀相關 episodic flaccid weakness，可與 channelopathy 或 thyrotoxicosis 相關。"),
    TopicSeed("condition", "acute-intermittent-porphyria", "Acute intermittent porphyria, AIP (急性間歇性紫質症)", ("Acute intermittent porphyria", "AIP", "紫質症", "porphyria"), "heme synthesis 缺陷造成腹痛、神經精神症狀、自律神經異常與 hyponatremia。"),
    TopicSeed("procedure", "intravenous-immunoglobulin", "Intravenous immunoglobulin, IVIG (靜脈免疫球蛋白)", ("IVIG", "intravenous immunoglobulin", "靜脈免疫球蛋白"), "免疫調節治療，可用於 GBS、CIDP、MG crisis 等免疫性神經疾病。"),
)


NINTH_BOOK_SEEDS: tuple[TopicSeed, ...] = (
    # Surgery fundamentals: nutrition, fluids, shock, complications, infection, transplant, trauma, ethics, endoscopy.
    TopicSeed("concept", "surgical-nutrition", "Surgical nutrition (外科營養)", ("外科營養", "surgical nutrition", "營養評估", "nutrition support"), "手術病人的營養狀態影響傷口癒合、感染、住院天數與預後，需評估 enteral/parenteral route 與再餵食風險。"),
    TopicSeed("procedure", "enteral-nutrition", "Enteral nutrition (腸道營養)", ("enteral nutrition", "腸道營養", "tube feeding"), "經腸胃道給予營養，腸道可用時通常優先於 parenteral nutrition。"),
    TopicSeed("procedure", "parenteral-nutrition", "Parenteral nutrition, PN/TPN (靜脈營養)", ("parenteral nutrition", "TPN", "靜脈營養", "total parenteral"), "經靜脈給予營養，適用於腸道不可用或需求無法由腸道滿足時，需監測感染、代謝與肝膽併發症。"),
    TopicSeed("condition", "refeeding-syndrome", "Refeeding syndrome (再餵食症候群)", ("refeeding", "再餵食", "hypophosphatemia"), "長期營養不良後快速補充營養可造成 hypophosphatemia、電解質移位與心肺神經併發症。"),
    TopicSeed("condition", "malnutrition", "Malnutrition (營養不良)", ("malnutrition", "營養不良", "albumin", "prealbumin"), "能量、蛋白質或微量營養素不足會增加手術併發症與感染風險。"),
    TopicSeed("condition", "shock", "Shock (休克)", ("shock", "休克", "低血壓", "organ perfusion"), "循環灌流不足造成組織缺氧與器官功能障礙，需依 hypovolemic、cardiogenic、distributive、obstructive 等機轉處置。"),
    TopicSeed("condition", "hypovolemic-shock", "Hypovolemic shock (低血容量性休克)", ("hypovolemic shock", "低血容量性休克", "volume depletion"), "血液或體液流失造成 preload 下降與灌流不足，治療重點是止血與補充容量。"),
    TopicSeed("condition", "hemorrhagic-shock", "Hemorrhagic shock (出血性休克)", ("hemorrhagic shock", "出血性休克", "massive hemorrhage"), "急性失血造成循環衰竭，需止血、輸血、凝血矯正與 damage control resuscitation。"),
    TopicSeed("condition", "septic-shock", "Septic shock (敗血性休克)", ("septic shock", "敗血性休克", "sepsis shock"), "感染造成血管擴張、微循環異常與器官灌流不足，需 source control、抗生素、輸液與血管升壓藥。"),
    TopicSeed("condition", "neurogenic-shock", "Neurogenic shock (神經性休克)", ("neurogenic shock", "神經性休克", "spinal shock"), "脊髓或交感路徑損傷造成血管張力下降與相對 bradycardia。"),
    TopicSeed("condition", "surgical-site-infection", "Surgical site infection, SSI (手術部位感染)", ("surgical site infection", "SSI", "手術部位感染", "傷口感染"), "手術切口或深部組織感染，風險與污染程度、宿主因子、抗生素預防與傷口照護相關。"),
    TopicSeed("condition", "wound-dehiscence", "Wound dehiscence (傷口裂開)", ("wound dehiscence", "傷口裂開", "dehiscence"), "手術傷口筋膜或皮膚分離，與感染、營養不良、腹壓、縫合張力與共病相關。"),
    TopicSeed("condition", "anastomotic-leak", "Anastomotic leak (吻合口滲漏)", ("anastomotic leak", "吻合口滲漏", "吻合處漏"), "腸胃道或血管吻合處破裂漏出，可能導致膿瘍、腹膜炎、敗血症。"),
    TopicSeed("condition", "postoperative-ileus", "Postoperative ileus (術後腸麻痺)", ("postoperative ileus", "術後腸麻痺", "ileus"), "手術後腸蠕動暫時下降，需與 mechanical obstruction、感染、電解質異常鑑別。"),
    TopicSeed("procedure", "fluid-resuscitation", "Fluid resuscitation (輸液復甦)", ("fluid resuscitation", "輸液復甦", "resuscitation fluid"), "以 crystalloid、blood products 或其他液體恢復有效循環容量與灌流，需依休克類型與出血量調整。"),
    TopicSeed("procedure", "massive-transfusion-protocol", "Massive transfusion protocol, MTP (大量輸血流程)", ("massive transfusion", "大量輸血", "MTP"), "大量出血時以固定比例血品快速補充紅血球、血漿、血小板並監測凝血與鈣。"),
    TopicSeed("procedure", "damage-control-surgery", "Damage control surgery (損傷控制手術)", ("damage control surgery", "損傷控制", "damage control"), "嚴重外傷或生理崩潰時先控制出血污染，延後 definitive repair。"),
    TopicSeed("concept", "lethal-triad-trauma", "Lethal triad of trauma (創傷致命三角)", ("lethal triad", "致命三角", "hypothermia", "acidosis", "coagulopathy"), "外傷出血後 hypothermia、acidosis、coagulopathy 互相惡化，是 damage control 的核心概念。"),
    TopicSeed("diagnostic", "focused-assessment-with-sonography-for-trauma", "FAST exam (創傷超音波快速評估)", ("FAST", "focused assessment", "創傷超音波"), "外傷病人床邊超音波快速評估腹腔、心包膜或胸腔液體。"),
    TopicSeed("condition", "abdominal-trauma", "Abdominal trauma (腹部創傷)", ("abdominal trauma", "腹部創傷", "blunt abdominal", "penetrating abdominal"), "腹部鈍傷或穿刺傷可能造成實質器官、腸道、血管與後腹腔損傷。"),
    TopicSeed("concept", "organ-transplantation", "Organ transplantation (器官移植)", ("organ transplantation", "器官移植", "移植種類", "移植外科"), "以活體或屍體捐贈器官取代末期器官衰竭，需評估配對、排斥、感染與倫理。"),
    TopicSeed("condition", "transplant-rejection", "Transplant rejection (移植排斥反應)", ("transplant rejection", "移植排斥", "hyperacute rejection", "acute rejection", "chronic rejection"), "受者免疫系統攻擊移植物，可分超急性、急性與慢性排斥。"),
    TopicSeed("diagnostic", "hla-crossmatch", "HLA typing and crossmatch (HLA 配對與交叉試驗)", ("HLA", "crossmatch", "配對檢驗", "交叉試驗"), "器官移植前評估 donor-recipient compatibility 與 preformed antibodies。"),
    TopicSeed("procedure", "lung-transplantation", "Lung transplantation (肺臟移植)", ("肺臟移植", "lung transplantation", "lung transplant"), "末期肺病的移植治療，需評估感染、惡性腫瘤、肺高壓與術後慢性排斥。"),
    TopicSeed("procedure", "organ-preservation", "Organ preservation (器官保存)", ("organ preservation", "器官保存", "cold ischemia"), "器官摘取後以低溫保存液與時間管理降低 ischemia-reperfusion injury。"),
    TopicSeed("procedure", "laparoscopy", "Laparoscopy (腹腔鏡)", ("laparoscopy", "腹腔鏡", "腹腔鏡手術"), "以小切口與鏡頭進入腹腔進行診斷或治療，可降低部分手術傷口與恢復負擔。"),
    TopicSeed("procedure", "thoracoscopy", "Thoracoscopy / VATS (胸腔鏡)", ("thoracoscopy", "VATS", "胸腔鏡"), "以胸腔鏡進行診斷、切片、肺部或縱膈手術。"),
    TopicSeed("concept", "medical-ethics", "Medical ethics (醫學倫理)", ("medical ethics", "醫學倫理", "autonomy", "beneficence", "non-maleficence", "justice"), "醫療決策中的自主、行善、不傷害、公平與知情同意等原則。"),
    TopicSeed("concept", "informed-consent", "Informed consent (知情同意)", ("informed consent", "知情同意", "告知同意"), "醫療處置前向病人說明診斷、處置、風險、替代方案與拒絕後果並取得同意。"),
    # Neurosurgery: coma, trauma, ICP, vascular disease.
    TopicSeed("condition", "coma", "Coma (昏迷)", ("coma", "昏迷", "意識障礙", "comatose"), "嚴重意識障礙，需以 GCS、瞳孔、腦幹反射、代謝與結構病灶快速評估。"),
    TopicSeed("condition", "brain-death", "Brain death (腦死)", ("brain death", "腦死", "腦死判定"), "全腦功能不可逆喪失，需符合嚴格臨床條件、排除干擾因素並依當地法規判定。"),
    TopicSeed("condition", "head-trauma", "Head trauma (頭部創傷)", ("head trauma", "頭部創傷", "head injury"), "頭部外傷可能造成顱骨骨折、EDH、SDH、腦挫傷、DAI、IICP 或腦疝。"),
    TopicSeed("condition", "traumatic-brain-injury", "Traumatic brain injury, TBI (創傷性腦損傷)", ("traumatic brain injury", "TBI", "創傷性腦損傷"), "外力造成腦功能或結構損傷，嚴重度依 GCS、影像、意識與神經缺損評估。"),
    TopicSeed("condition", "epidural-hematoma", "Epidural hematoma, EDH (硬腦膜上血腫)", ("Epidural hematoma", "EDH", "硬腦膜上", "lucid interval"), "顱骨與 dura 間出血，常與 middle meningeal artery 損傷和 lucid interval 相關。"),
    TopicSeed("condition", "subdural-hematoma", "Subdural hematoma, SDH (硬腦膜下血腫)", ("Subdural hematoma", "SDH", "硬腦膜下", "bridging vein"), "bridging veins 破裂造成 dura 與 arachnoid 間出血，可為急性、亞急性或慢性。"),
    TopicSeed("condition", "diffuse-axonal-injury", "Diffuse axonal injury, DAI (瀰漫性軸索損傷)", ("diffuse axonal", "DAI", "瀰漫性軸索"), "加減速剪力造成白質軸索損傷，常有昏迷但 CT 初期可能不明顯。"),
    TopicSeed("condition", "cerebral-contusion", "Cerebral contusion (腦挫傷)", ("cerebral contusion", "腦挫傷", "contrecoup"), "腦實質挫傷出血，常見於額顳葉，可有 edema、seizure 或 delayed deterioration。"),
    TopicSeed("condition", "skull-fracture", "Skull fracture (顱骨骨折)", ("skull fracture", "顱骨骨折", "basilar skull fracture"), "顱骨骨折可提示高能量外傷，需注意 CSF leak、血管損傷與顱內出血。"),
    TopicSeed("concept", "monro-kellie-doctrine", "Monro-Kellie doctrine (Monro-Kellie 學說)", ("Monro-Kellie", "孟洛", "顱內容積"), "顱腔內腦組織、血液、CSF 總量相對固定，任一成分增加會使 ICP 上升。"),
    TopicSeed("diagnostic", "intracranial-pressure-monitoring", "Intracranial pressure monitoring, ICP monitoring (顱內壓監測)", ("ICP monitoring", "顱內壓監測", "ICP 監測"), "以 invasive monitor 追蹤顱內壓，協助嚴重 TBI、SAH、ICH 或 IICP 治療決策。"),
    TopicSeed("drug", "mannitol", "Mannitol (甘露醇)", ("Mannitol", "甘露醇"), "滲透性利尿劑，可暫時降低顱內壓；需監測滲透壓、腎功能與容量狀態。"),
    TopicSeed("drug", "hypertonic-saline", "Hypertonic saline (高張食鹽水)", ("hypertonic saline", "高張食鹽水", "3% saline"), "高張液可用於 IICP 或低血鈉矯正，需監測鈉上升速度與滲透壓。"),
    TopicSeed("procedure", "decompressive-craniectomy", "Decompressive craniectomy (減壓顱骨切除術)", ("decompressive craniectomy", "減壓顱骨", "decompressive craniectormy"), "移除部分顱骨以降低 refractory IICP 或大面積腦梗塞/外傷腦腫脹壓力。"),
    TopicSeed("condition", "cerebral-vasospasm", "Cerebral vasospasm (腦血管痙攣)", ("vasospasm", "血管痙攣", "cerebral vasospasm"), "SAH 後 delayed vasospasm 可造成 delayed cerebral ischemia。"),
    TopicSeed("condition", "cavernous-malformation", "Cavernous malformation (海綿狀血管畸形)", ("Cavernous malformation", "海綿狀血管畸形", "cavernoma"), "低流量血管畸形，可造成出血、seizure 或偶然發現。"),
    TopicSeed("condition", "carotid-cavernous-fistula", "Carotid-cavernous fistula, CCF (頸動脈海綿竇瘻管)", ("Carotid-cavernous fistula", "CCF", "頸動脈海綿竇瘻"), "頸動脈與 cavernous sinus 異常交通，可造成突眼、結膜充血、眼肌麻痺與雜音。"),
    TopicSeed("condition", "hydrocephalus", "Hydrocephalus (水腦症)", ("hydrocephalus", "水腦症", "ventriculomegaly"), "CSF 生成、循環或吸收異常造成腦室擴大與顱內壓或步態/認知/尿失禁症狀。"),
    TopicSeed("condition", "normal-pressure-hydrocephalus", "Normal pressure hydrocephalus, NPH (正常壓力水腦症)", ("Normal pressure hydrocephalus", "NPH", "正常壓力水腦"), "以 gait disturbance、urinary incontinence、cognitive decline 為典型 triad 的 communicating hydrocephalus。"),
    TopicSeed("procedure", "ventriculoperitoneal-shunt", "Ventriculoperitoneal shunt, VP shunt (腦室腹腔分流術)", ("VP shunt", "ventriculoperitoneal", "腦室腹腔分流"), "將腦室 CSF 分流至腹腔以治療 hydrocephalus。"),
    TopicSeed("procedure", "external-ventricular-drain", "External ventricular drain, EVD (體外腦室引流)", ("EVD", "external ventricular drain", "體外腦室引流"), "暫時性腦室引流，可用於 acute hydrocephalus、ICP monitoring 或 SAH/IVH。"),
    TopicSeed("condition", "trigeminal-neuralgia", "Trigeminal neuralgia (三叉神經痛)", ("Trigeminal neuralgia", "三叉神經痛", "tic douloureux"), "三叉神經分布短暫劇烈電擊樣疼痛，常由血管壓迫或 demyelination 相關。"),
    TopicSeed("procedure", "microvascular-decompression", "Microvascular decompression, MVD (微血管減壓術)", ("microvascular decompression", "MVD", "微血管減壓"), "解除神經受血管壓迫的手術，常用於 trigeminal neuralgia。"),
    # Spine and neurosurgical tumors.
    TopicSeed("condition", "herniated-intervertebral-disc", "Herniated intervertebral disc, HIVD (椎間盤突出)", ("Herniated Intervertebral Disc", "HIVD", "椎間盤突出"), "椎間盤髓核突出壓迫神經根或脊髓，常見腰椎 radiculopathy 或頸椎 myelopathy。"),
    TopicSeed("condition", "spinal-stenosis", "Spinal stenosis (脊椎狹窄)", ("Spinal stenosis", "脊椎狹窄", "neurogenic claudication"), "椎管或神經孔狹窄造成神經壓迫，腰椎可表現 neurogenic claudication。"),
    TopicSeed("condition", "cervical-myelopathy", "Cervical myelopathy (頸椎脊髓病變)", ("cervical myelopathy", "頸椎狹窄", "頸髓病變"), "頸椎狹窄或壓迫造成上運動神經元徵象、手部靈活度下降與步態不穩。"),
    TopicSeed("condition", "spinal-cord-injury", "Spinal cord injury, SCI (脊髓損傷)", ("Spinal injuries", "spinal cord injury", "SCI", "脊髓創傷", "脊髓損傷"), "外傷造成脊髓功能受損，需初步固定、神經分級、影像與併發症管理。"),
    TopicSeed("condition", "cervical-spine-fracture", "Cervical spine fracture (頸椎骨折)", ("Cervical spine fracture", "頸椎骨折", "C1 fracture", "Hangman's fracture"), "頸椎骨折可威脅脊髓與椎動脈，需依穩定性與神經狀態處置。"),
    TopicSeed("condition", "spondylolisthesis", "Spondylolisthesis (脊椎滑脫)", ("Spondylolisthesis", "脊椎滑脱", "脊椎滑脫"), "上位椎體相對下位椎體滑移，可造成背痛、radiculopathy 或神經性跛行。"),
    TopicSeed("condition", "scoliosis", "Scoliosis (脊椎側彎)", ("scoliosis", "脊椎側彎", "Cobb angle"), "冠狀面脊柱側彎，需依 Cobb angle、年齡與進展風險追蹤或治療。"),
    TopicSeed("condition", "spinal-tumor", "Spinal tumor / spinal cord tumor (脊椎與脊髓腫瘤)", ("spinal cord tumor", "spinal tumor", "脊椎與脊髓腫瘤"), "脊椎、硬膜外、髓內或髓外腫瘤可造成疼痛、神經根症狀或脊髓壓迫。"),
    TopicSeed("condition", "spina-bifida", "Spina bifida (脊柱裂)", ("Spina bifida", "脊柱裂", "myelomeningocele"), "神經管閉合不全疾病，可伴隨脊髓膜膨出、神經缺損與 Chiari II/hydrocephalus。"),
    TopicSeed("condition", "brain-tumor", "Brain tumor (腦瘤)", ("Brain Tumors", "brain tumor", "腦瘤", "intracranial tumor"), "顱內腫瘤依組織來源、位置與 grade 造成 seizure、IICP、focal deficit 或 endocrine symptoms。"),
    TopicSeed("condition", "glioma", "Glioma (神經膠質瘤)", ("Glioma", "神經膠質瘤", "astrocytoma", "oligodendroglioma", "glioblastoma"), "源自 glial cells 的 CNS 腫瘤群，包含 astrocytoma、oligodendroglioma、glioblastoma 等。"),
    TopicSeed("condition", "glioblastoma", "Glioblastoma, GBM (膠質母細胞瘤)", ("Glioblastoma", "GBM", "膠質母細胞"), "WHO grade 4 diffuse glioma，侵襲性高，影像常有 ring enhancement 與 necrosis。"),
    TopicSeed("condition", "astrocytoma", "Astrocytoma (星狀細胞瘤)", ("Astrocytoma", "星狀細胞瘤"), "astrocytic tumor，臨床與預後依分子分類與 grade 而異。"),
    TopicSeed("condition", "oligodendroglioma", "Oligodendroglioma (寡樹突神經膠瘤)", ("Oligodendroglioma", "寡樹突神經膠瘤", "fried egg"), "常具 IDH mutation 與 1p/19q codeletion，影像可見鈣化。"),
    TopicSeed("condition", "ependymoma", "Ependymoma (室管膜瘤)", ("Ependymoma", "室管膜瘤"), "源自 ependymal cells，可位於腦室或脊髓中央管附近。"),
    TopicSeed("condition", "choroid-plexus-tumor", "Choroid plexus tumor (脈絡叢腫瘤)", ("Choroid plexus tumor", "脈絡叢腫瘤"), "脈絡叢來源腫瘤，可造成 CSF 過度生成或阻塞性 hydrocephalus。"),
    TopicSeed("condition", "medulloblastoma", "Medulloblastoma (髓母細胞瘤)", ("Medulloblastoma", "髓母細胞瘤"), "兒童後顱窩惡性胚胎性腫瘤，可經 CSF 播散。"),
    TopicSeed("condition", "vestibular-schwannoma", "Vestibular schwannoma / acoustic neuroma (前庭神經鞘瘤／聽神經瘤)", ("Vestibular schwannoma", "acoustic neuroma", "聽神經瘤"), "第八腦神經 Schwann cell 腫瘤，造成單側聽損、耳鳴、平衡障礙，可與 NF2 相關。"),
    TopicSeed("condition", "meningioma", "Meningioma (腦膜瘤)", ("Meningioma", "腦膜瘤", "dural tail"), "源自 arachnoid cap cells 的常見成人顱內腫瘤，多數良性且可有 dural tail。"),
    TopicSeed("condition", "hemangioblastoma", "Hemangioblastoma (血管母細胞瘤)", ("Hemangioblastoma", "血管母細胞瘤"), "血管性 CNS 腫瘤，可與 von Hippel-Lindau disease 相關。"),
    TopicSeed("condition", "craniopharyngioma", "Craniopharyngioma (顱咽瘤)", ("Craniopharyngioma", "顱咽瘤", "Rathke"), "鞍上區腫瘤，可造成視交叉壓迫、內分泌異常與鈣化囊性病灶。"),
    TopicSeed("condition", "intracranial-germ-cell-tumor", "Intracranial germ cell tumor (顱內生殖細胞腫瘤)", ("germ cell tumors", "GCT", "胚細胞腫瘤", "生殖細胞腫瘤"), "顱內 germ cell tumors 常位於 pineal 或 suprasellar region，可有 endocrine 或 hydrocephalus 表現。"),
    TopicSeed("condition", "epidermoid-cyst", "Epidermoid cyst/tumor (表皮樣囊腫)", ("Epidermoid tumor", "epidermoid cyst", "表皮樣囊腫"), "先天性 inclusion cyst，常位於 cerebellopontine angle，影像與症狀可似腫瘤。"),
    TopicSeed("condition", "idiopathic-intracranial-hypertension", "Idiopathic intracranial hypertension / pseudotumor cerebri (特發性顱內高壓／大腦假性腫瘤)", ("Pseudotumor cerebri", "idiopathic intracranial hypertension", "大腦假性腫瘤"), "無明顯腫塊或 hydrocephalus 的 IICP，常見於年輕肥胖女性，可造成 papilledema 與視力風險。"),
)


TENTH_BOOK_SEEDS: tuple[TopicSeed, ...] = (
    # Cardiovascular surgery: aorta, valve, peripheral vascular disease, heart transplant.
    TopicSeed("condition", "peripheral-arterial-disease", "Peripheral arterial disease / PAOD (周邊動脈阻塞疾病)", ("Peripheral artery occlusion disease", "PAOD", "周邊動脈阻塞", "intermittent claudication"), "下肢或周邊動脈粥狀硬化狹窄造成 claudication、休息痛、ulcer/gangrene，需評估危險因子、ABI 與血管重建時機。"),
    TopicSeed("condition", "acute-limb-ischemia", "Acute limb ischemia (急性肢體缺血)", ("acute limb ischemia", "急性肢體缺血", "six P", "6 P"), "動脈急性阻塞造成 limb-threatening ischemia，典型以 pain、pallor、pulselessness、paresthesia、paralysis、poikilothermia 評估。"),
    TopicSeed("condition", "critical-limb-ischemia", "Critical limb ischemia (重症肢體缺血)", ("critical limb ischemia", "重症肢體缺血", "rest pain", "gangrene"), "慢性嚴重周邊動脈阻塞造成休息痛、潰瘍或壞疽，需考慮 revascularization 與傷口照護。"),
    TopicSeed("diagnostic", "ankle-brachial-index", "Ankle-brachial index, ABI (踝肱指數)", ("ankle-brachial index", "ABI", "踝肱指數"), "以下肢與上肢收縮壓比值評估 peripheral arterial disease 嚴重度與追蹤治療反應。"),
    TopicSeed("procedure", "endovascular-aneurysm-repair", "Endovascular aneurysm repair, EVAR (血管內主動脈瘤修補)", ("EVAR", "endovascular aneurysm repair", "血管內主動脈瘤"), "以支架 graft 經血管內修補腹主動脈瘤，需注意 endoleak、解剖適應症與長期追蹤。"),
    TopicSeed("procedure", "aortic-dissection-surgery", "Aortic dissection surgery (主動脈剝離手術)", ("主動脈剝離手術", "Type A", "ascending aorta replacement", "anti-impulse therapy"), "Type A aortic dissection 通常需急診手術；Type B 多先內科 anti-impulse therapy，併發症時考慮 TEVAR 或手術。"),
    TopicSeed("procedure", "valve-replacement-repair", "Valve replacement/repair (瓣膜置換與修補)", ("valve replacement", "valve repair", "瓣膜置換", "瓣膜修補", "mechanical valve", "bioprosthetic"), "瓣膜病變可依病因、嚴重度、症狀與手術風險選擇 repair 或 replacement，並需考慮抗凝需求。"),
    TopicSeed("procedure", "heart-transplantation", "Heart transplantation (心臟移植)", ("heart transplantation", "heart transplant", "心臟移植"), "末期心衰竭的外科治療之一，需評估適應症、禁忌症、排斥、感染與免疫抑制。"),
    # Colorectal surgery.
    TopicSeed("condition", "colonic-volvulus", "Colonic volvulus (大腸扭轉)", ("腸扭結", "volvulus", "sigmoid volvulus", "cecal volvulus"), "大腸腸段沿腸繫膜扭轉造成閉塞與缺血風險，常見於 sigmoid 與 cecum。"),
    TopicSeed("condition", "colonic-pseudo-obstruction", "Colonic pseudo-obstruction / Ogilvie syndrome (偽結腸阻塞)", ("Colonic pseudo-obstruction", "Ogilvie", "偽結腸阻塞"), "無機械性阻塞卻出現急性大腸擴張，常見於重病、術後或電解質異常，需避免穿孔。"),
    TopicSeed("condition", "diverticular-disease", "Diverticular disease (大腸憩室疾病)", ("大腸憩室", "diverticular disease", "diverticulosis", "diverticulitis"), "大腸憩室可無症狀，也可造成 diverticulitis、出血、膿瘍、穿孔或狹窄。"),
    TopicSeed("condition", "diverticulitis", "Diverticulitis (憩室炎)", ("diverticulitis", "憩室炎", "Hinchey"), "憩室發炎感染造成腹痛、發燒與局部腹膜刺激，併發症可包含膿瘍、穿孔、瘻管或阻塞。"),
    TopicSeed("condition", "colonic-angiodysplasia", "Colonic angiodysplasia (大腸血管發育不良)", ("angiodysplasia", "血管異常", "arteriovenous malformation", "cecal AVM"), "退化性黏膜下血管擴張是下消化道出血原因之一，常見於右側大腸與高齡病人。"),
    TopicSeed("condition", "colorectal-polyp", "Colorectal polyp (大腸直腸息肉)", ("息肉", "colorectal polyp", "adenomatous polyp", "villous adenoma"), "大腸直腸息肉依組織型與大小決定癌化風險，adenoma-carcinoma sequence 是篩檢重點。"),
    TopicSeed("condition", "familial-adenomatous-polyposis", "Familial adenomatous polyposis, FAP (家族性腺瘤性息肉症)", ("Familial adenomatous polyposis", "FAP", "APC", "Gardner", "Turcot"), "APC mutation 造成大量腺瘤性息肉與高度 colorectal cancer 風險，需基因與內視鏡篩檢及預防性手術規劃。"),
    TopicSeed("condition", "lynch-syndrome", "Lynch syndrome / HNPCC (林奇症候群／遺傳性非息肉性大腸癌)", ("HNPCC", "Lynch", "defective mismatch repair", "MSH2", "MLH1"), "mismatch repair gene 缺陷造成右側大腸癌與子宮內膜癌等風險上升，息肉數通常不多。"),
    TopicSeed("condition", "appendicitis", "Appendicitis (闌尾炎)", ("闌尾炎", "appendicitis", "McBurney", "Rovsing"), "闌尾管腔阻塞後感染發炎，表現可由臍周痛轉右下腹痛，需注意穿孔與膿瘍。"),
    TopicSeed("condition", "hemorrhoids", "Hemorrhoids (痔瘡)", ("痔瘡", "hemorrhoid", "internal hemorrhoid", "external hemorrhoid"), "肛墊血管組織腫大或脫垂，可造成無痛性出血、疼痛、搔癢或血栓性外痔。"),
    TopicSeed("condition", "anal-fissure", "Anal fissure (肛裂)", ("Anal fissure", "肛裂", "posterior midline fissure"), "肛管裂傷造成排便疼痛與鮮血，慢性肛裂與內括約肌高張相關。"),
    TopicSeed("condition", "anorectal-abscess-fistula", "Anorectal abscess and fistula (肛門直腸膿瘍與瘻管)", ("肛門膿瘍", "肛門瘻管", "anorectal abscess", "fistula-in-ano"), "肛門腺感染可形成膿瘍，破裂或引流後可能形成 fistula-in-ano。"),
    TopicSeed("procedure", "colectomy", "Colectomy (大腸切除術)", ("colectomy", "hemicolectomy", "subtotal colectomy", "大腸切除"), "依病灶位置與病因切除部分或全部大腸，常用於 colorectal cancer、IBD、diverticular disease 或急性阻塞/穿孔。"),
    TopicSeed("procedure", "low-anterior-resection", "Low anterior resection, LAR (低位前切除術)", ("Low anterior resection", "LAR", "低位前切除"), "保留括約肌的直腸癌手術，需注意 distal margin、anastomotic leak 與暫時性 diversion。"),
    TopicSeed("procedure", "abdominoperineal-resection", "Abdominoperineal resection, APR (腹會陰聯合切除術)", ("Abdominoperineal resection", "APR", "腹會陰"), "直腸癌侵犯或接近括約肌時可能需移除直腸與肛門並建立永久 colostomy。"),
    TopicSeed("procedure", "ostomy", "Ostomy (腸造口)", ("ostomy", "stoma", "colostomy", "ileostomy", "腸造口", "人工肛門"), "將腸道開口接至腹壁以排便或 diversion，需術前定位與術後照護。"),
    TopicSeed("procedure", "appendectomy", "Appendectomy (闌尾切除術)", ("appendectomy", "闌尾切除", "laparoscopic appendectomy"), "急性闌尾炎常見手術治療，可採開腹或腹腔鏡方式，需依穿孔、膿瘍與病人狀況調整。"),
    # Endocrine surgery.
    TopicSeed("condition", "goiter", "Goiter (甲狀腺腫)", ("goiter", "甲狀腺腫", "diffuse goiter", "nodular goiter"), "甲狀腺腫大可為 diffuse 或 nodular，功能可亢進、低下或正常，需依症狀、功能與惡性風險評估。"),
    TopicSeed("condition", "subacute-thyroiditis", "Subacute thyroiditis / de Quervain thyroiditis (亞急性甲狀腺炎)", ("Subacute thyroiditis", "de Quervain", "亞急性甲狀腺炎"), "常在病毒感染後發生疼痛性甲狀腺炎，甲狀腺功能可先亢進後低下再恢復。"),
    TopicSeed("condition", "papillary-thyroid-carcinoma", "Papillary thyroid carcinoma (乳突狀甲狀腺癌)", ("papillary thyroid carcinoma", "乳突狀甲狀腺癌", "Orphan Annie eye", "psammoma"), "最常見甲狀腺癌，常經淋巴轉移，預後通常較佳但需依風險分層治療。"),
    TopicSeed("condition", "follicular-thyroid-carcinoma", "Follicular thyroid carcinoma (濾泡狀甲狀腺癌)", ("follicular thyroid carcinoma", "濾泡狀甲狀腺癌", "capsular invasion"), "濾泡來源惡性腫瘤，診斷重點為包膜或血管侵犯，較常血行轉移。"),
    TopicSeed("condition", "medullary-thyroid-carcinoma", "Medullary thyroid carcinoma (髓質甲狀腺癌)", ("medullary thyroid carcinoma", "髓質甲狀腺癌", "calcitonin", "RET"), "C cell 來源甲狀腺癌，與 calcitonin、RET mutation、MEN2 相關。"),
    TopicSeed("condition", "anaplastic-thyroid-carcinoma", "Anaplastic thyroid carcinoma (未分化甲狀腺癌)", ("anaplastic thyroid carcinoma", "未分化甲狀腺癌"), "侵襲性極高的甲狀腺癌，可快速造成頸部壓迫與 airway 風險。"),
    TopicSeed("procedure", "thyroidectomy", "Thyroidectomy (甲狀腺切除術)", ("thyroidectomy", "甲狀腺切除", "subtotal thyroidectomy", "total thyroidectomy"), "用於部分 Graves disease、甲狀腺結節或甲狀腺癌；需注意出血、hypocalcemia、recurrent laryngeal nerve injury。"),
    TopicSeed("diagnostic", "thyroid-ultrasonography", "Thyroid ultrasonography (甲狀腺超音波)", ("Thyroid ultrasonography", "甲狀腺超音波", "hypoechoic", "microcalcification"), "評估 thyroid nodule 的 cystic/solid、鈣化、邊緣、血流與 FNA 導引。"),
    TopicSeed("diagnostic", "fine-needle-aspiration-cytology", "Fine needle aspiration cytology, FNA (細針抽吸細胞學)", ("Fine needle aspiration", "FNA", "細針抽吸", "cytology"), "甲狀腺結節與其他表淺腫塊常用細胞學檢查，用於良惡性分流與手術決策。"),
    TopicSeed("condition", "parathyroid-carcinoma", "Parathyroid carcinoma (副甲狀腺癌)", ("Parathyroid carcinoma", "副甲狀腺癌"), "少見但可造成嚴重 hypercalcemia 的副甲狀腺惡性腫瘤，治療以完整切除為主。"),
    TopicSeed("procedure", "parathyroidectomy", "Parathyroidectomy (副甲狀腺切除術)", ("parathyroidectomy", "副甲狀腺切除", "minimally invasive parathyroidectomy"), "用於符合手術條件的 primary hyperparathyroidism 或副甲狀腺腫瘤，需監測術後低血鈣與 hungry bone syndrome。"),
    TopicSeed("condition", "insulinoma", "Insulinoma (胰島素瘤)", ("insulinoma", "胰島素瘤", "Whipple triad"), "分泌 insulin 的 pancreatic neuroendocrine tumor，造成 fasting hypoglycemia 與 Whipple triad。"),
    TopicSeed("condition", "gastrinoma", "Gastrinoma / Zollinger-Ellison syndrome (胃泌素瘤／Zollinger-Ellison 症候群)", ("gastrinoma", "Zollinger", "胃泌素瘤"), "gastrin 分泌腫瘤造成 refractory peptic ulcer disease、胃酸過多與腹瀉，可與 MEN1 相關。"),
    TopicSeed("condition", "vipoma", "VIPoma (血管活性腸胜肽瘤)", ("VIPoma", "WDHA", "VIP 瘤", "watery diarrhea"), "分泌 vasoactive intestinal peptide 的 neuroendocrine tumor，可造成 watery diarrhea、hypokalemia、achlorhydria。"),
    TopicSeed("condition", "glucagonoma", "Glucagonoma (升糖素瘤)", ("glucagonoma", "升糖素瘤", "necrolytic migratory erythema"), "分泌 glucagon 的 pancreatic neuroendocrine tumor，可有糖尿病、體重下降、貧血與 necrolytic migratory erythema。"),
    TopicSeed("condition", "multiple-endocrine-neoplasia", "Multiple endocrine neoplasia, MEN (多發性內分泌腫瘤症候群)", ("Multiple endocrine neoplasia", "MEN", "多發性內分泌腫瘤"), "遺傳性內分泌腫瘤症候群，MEN1 與 MEN2 影響的腺體、基因與篩檢不同。"),
    TopicSeed("condition", "men1-syndrome", "MEN1 syndrome (第一型多發性內分泌腫瘤)", ("MEN1", "Wermer", "parathyroid", "pituitary", "pancreatic"), "MEN1 常涉及 parathyroid、pituitary 與 pancreatic neuroendocrine tumors。"),
    TopicSeed("condition", "men2-syndrome", "MEN2 syndrome (第二型多發性內分泌腫瘤)", ("MEN2", "Sipple", "RET", "medullary thyroid", "pheochromocytoma"), "MEN2 與 RET mutation、medullary thyroid carcinoma、pheochromocytoma 及 hyperparathyroidism 相關。"),
    TopicSeed("condition", "adrenal-incidentaloma", "Adrenal incidentaloma (腎上腺偶發瘤)", ("adrenal incidentaloma", "腎上腺偶發瘤", "incidental adrenal mass"), "影像偶然發現的腎上腺腫塊需評估功能性分泌與惡性風險。"),
    TopicSeed("procedure", "adrenalectomy", "Adrenalectomy (腎上腺切除術)", ("adrenalectomy", "腎上腺切除", "laparoscopic adrenalectomy"), "用於部分功能性腎上腺腫瘤或疑似惡性病灶；pheochromocytoma 術前需充分 alpha blockade。"),
    # Reconstructive and plastic surgery.
    TopicSeed("condition", "pressure-injury", "Pressure injury / pressure sore (壓傷／壓瘡)", ("Pressure sore", "pressure injury", "壓瘡", "褥瘡"), "長期受壓造成皮膚與深部組織損傷，需依分期、感染、營養與重建需求處理。"),
    TopicSeed("procedure", "skin-graft", "Skin graft (皮膚移植)", ("Skin Graft", "skin graft", "皮膚移植", "STSG", "FTSG"), "將皮膚從 donor site 移至 recipient bed，分 split-thickness 與 full-thickness graft，存活依 plasmatic imbibition、inosculation 與 revascularization。"),
    TopicSeed("procedure", "surgical-flap", "Surgical flap (皮瓣手術)", ("Surgical Flap", "皮瓣", "flap surgery", "random flap", "axial flap"), "帶有血供的組織轉移用於重建缺損，可依血流、組織組成與移動方式分類。"),
    TopicSeed("procedure", "cleft-lip-palate-repair", "Cleft lip/palate repair (唇顎裂修補)", ("cleft lip repair", "cleft palate repair", "唇裂修補", "顎裂修補"), "唇顎裂需分階段修補與語言、牙科、耳鼻喉、心理照護整合。"),
    TopicSeed("condition", "syndactyly", "Syndactyly (併指畸形)", ("syndactyly", "併指", "webbed fingers"), "手指分離不全，可為 simple/complex、complete/incomplete，治療需避免 web creep 與保護血供。"),
    TopicSeed("condition", "polydactyly", "Polydactyly (多指症)", ("polydactyly", "多指症", "extra digit"), "多餘手指或腳趾，可依位置分 preaxial、central、postaxial，手術需考慮功能與外觀。"),
    TopicSeed("procedure", "blepharoplasty", "Blepharoplasty (眼瞼整形術)", ("Blepharoplasty", "眼瞼整形", "眼皮整形"), "眼瞼整形可處理上眼瞼皮膚鬆弛、眼袋或功能性視野遮蔽，需評估眼乾與眼瞼位置。"),
    TopicSeed("procedure", "breast-augmentation", "Breast augmentation (隆乳手術)", ("Breast augmentation", "隆乳", "breast implant"), "以植入物或自體脂肪增加乳房體積，需了解植入物位置、切口、併發症與長期追蹤。"),
    TopicSeed("anatomy", "anal-canal", "Anal canal (肛管)", ("Anal canal", "肛管", "dentate line", "pectinate line"), "肛管解剖包含 dentate line、內外括約肌、血管與淋巴引流，決定痔瘡、肛裂、膿瘍與直腸癌處置。"),
    TopicSeed("physiology", "colorectal-physiology", "Colorectal physiology (大腸直腸生理)", ("大腸生理", "colorectal physiology", "colonic motility", "defecation"), "大腸負責水分電解質吸收、菌叢代謝與糞便儲存排出；肛門括約肌與直腸感覺參與 continence。"),
)


ELEVENTH_BOOK_SEEDS: tuple[TopicSeed, ...] = (
    # Stomach and foregut surgery.
    TopicSeed("condition", "gastric-outlet-obstruction", "Gastric outlet obstruction (胃出口阻塞)", ("Gastric outlet obstruction", "胃出口阻塞", "pyloric obstruction"), "胃或十二指腸出口阻塞造成嘔吐、早飽、脫水與電解質異常，常見原因包含潰瘍瘢痕與惡性腫瘤。"),
    TopicSeed("condition", "perforated-peptic-ulcer", "Perforated peptic ulcer (消化性潰瘍穿孔)", ("Perforated peptic ulcer", "PPU", "潰瘍穿孔", "free air"), "消化性潰瘍穿孔可造成急性腹膜炎與 pneumoperitoneum，需要復甦、抗生素與手術或內視鏡策略評估。"),
    TopicSeed("procedure", "gastrectomy", "Gastrectomy (胃切除術)", ("gastrectomy", "胃切除", "subtotal gastrectomy", "total gastrectomy"), "胃癌或複雜潰瘍可需部分或全胃切除，並依病灶位置與淋巴清除需求選擇重建方式。"),
    TopicSeed("procedure", "vagotomy", "Vagotomy (迷走神經切斷術)", ("vagotomy", "迷走神經阻斷", "迷走神經切斷"), "透過切斷 vagal input 降低胃酸分泌，傳統上用於潰瘍手術策略，常需搭配 drainage procedure。"),
    TopicSeed("procedure", "billroth-reconstruction", "Billroth reconstruction (Billroth 胃腸重建)", ("Billroth I", "Billroth II", "Billroth reconstruction"), "胃切除後可用 Billroth I 或 II 重建胃腸連續性，影響膽汁逆流、dumping 與 loop syndrome 風險。"),
    TopicSeed("procedure", "roux-en-y-reconstruction", "Roux-en-Y reconstruction (Roux-en-Y 重建)", ("Roux-en-Y", "Roux stasis"), "以 Roux limb 重建消化道連續性，可降低膽汁逆流但可能有 Roux stasis syndrome。"),
    TopicSeed("condition", "dumping-syndrome", "Dumping syndrome (傾倒症候群)", ("Dumping syndrome", "傾倒症候群", "postgastrectomy"), "胃切除後高滲食物快速進入小腸造成早期血管運動症狀或晚期低血糖。"),
    TopicSeed("condition", "afferent-loop-syndrome", "Afferent loop syndrome (輸入袢症候群)", ("Afferent loop syndrome", "輸入袢", "afferent loop"), "Billroth II 或相關重建後輸入袢阻塞造成膽胰液鬱積、腹痛、嘔吐或膽管胰臟併發症。"),
    TopicSeed("condition", "alkaline-reflux-gastritis", "Alkaline reflux gastritis (鹼性逆流性胃炎)", ("Alkaline reflux gastritis", "鹼性逆流", "bile reflux gastritis"), "胃手術後膽汁與胰液逆流刺激胃黏膜，可造成上腹痛、噁心與嘔吐。"),
    # Small bowel surgery.
    TopicSeed("condition", "small-bowel-obstruction", "Small bowel obstruction (小腸阻塞)", ("small bowel obstruction", "SBO", "小腸阻塞", "mechanical ileus", "stack of coin"), "小腸機械性阻塞常因術後沾黏、疝氣、腫瘤或腸扭結造成，需評估絞扼與缺血風險。"),
    TopicSeed("condition", "adhesive-small-bowel-obstruction", "Adhesive small bowel obstruction (沾黏性小腸阻塞)", ("adhesion ileus", "腸沾黏", "adhesive obstruction"), "腹部手術後沾黏是成人小腸阻塞常見原因，多數先支持療法，但惡化或絞扼需手術。"),
    TopicSeed("condition", "strangulated-bowel-obstruction", "Strangulated bowel obstruction (絞扼性腸阻塞)", ("strangulation", "絞扼性腸阻塞", "bowel ischemia", "peritoneal sign"), "腸阻塞合併血流受阻會導致缺血、壞死與穿孔，是需緊急處置的外科急症。"),
    TopicSeed("condition", "small-bowel-tumor", "Small bowel tumor (小腸腫瘤)", ("Tumors of small intestine", "small bowel tumor", "小腸腫瘤", "小腸癌"), "小腸腫瘤可為良性或惡性，症狀常不特異，可造成出血、阻塞、穿孔或腸套疊。"),
    TopicSeed("condition", "small-bowel-adenocarcinoma", "Small bowel adenocarcinoma (小腸腺癌)", ("small bowel adenocarcinoma", "小腸腺癌", "duodenal adenocarcinoma"), "小腸惡性腫瘤之一，與 Crohn disease、celiac disease、FAP 等風險相關。"),
    TopicSeed("condition", "gastrointestinal-carcinoid-tumor", "Gastrointestinal carcinoid tumor (胃腸道類癌)", ("carcinoid", "類癌", "neuroendocrine tumor", "5-HIAA"), "胃腸道 neuroendocrine tumor 可分泌 serotonin 等物質，轉移後可能造成 carcinoid syndrome。"),
    TopicSeed("condition", "carcinoid-syndrome", "Carcinoid syndrome (類癌症候群)", ("carcinoid syndrome", "類癌症候群", "flushing", "5-HIAA"), "類癌腫瘤分泌物進入體循環後可造成 flushing、diarrhea、bronchospasm 與右心瓣膜病變。"),
    # Liver surgery and tumors.
    TopicSeed("condition", "hepatic-hemangioma", "Hepatic hemangioma (肝血管瘤)", ("hepatic hemangioma", "肝血管瘤", "cavernous hemangioma"), "常見良性肝腫瘤，多數偶然發現且無症狀，影像典型時通常追蹤即可。"),
    TopicSeed("condition", "focal-nodular-hyperplasia", "Focal nodular hyperplasia, FNH (局部結節性增生)", ("focal nodular hyperplasia", "FNH", "局部結節性增生", "central scar"), "良性肝細胞增生病灶，常見於年輕女性，影像可見 central scar。"),
    TopicSeed("condition", "hepatic-adenoma", "Hepatic adenoma (肝腺瘤)", ("hepatic adenoma", "肝腺瘤", "oral contraceptive"), "良性肝細胞腫瘤，與 estrogen exposure 等相關，需注意出血與惡性轉化風險。"),
    TopicSeed("procedure", "hepatectomy", "Hepatectomy / liver resection (肝切除術)", ("hepatectomy", "liver resection", "肝切除"), "肝臟腫瘤或部分膿瘍/創傷可需肝切除，需評估肝功能、剩餘肝容量與腫瘤分布。"),
    TopicSeed("procedure", "radiofrequency-ablation", "Radiofrequency ablation, RFA (射頻燒灼治療)", ("radiofrequency ablation", "RFA", "射頻燒灼"), "以熱能局部消融肝腫瘤等病灶，常用於特定 HCC 或轉移病灶。"),
    # Biliary surgery.
    TopicSeed("condition", "acute-acalculous-cholecystitis", "Acute acalculous cholecystitis (急性非結石性膽囊炎)", ("Acute Acalculous Cholecystitis", "急性非結石性膽囊炎", "acalculous cholecystitis"), "重症、外傷、燒傷或禁食病人可發生無結石膽囊炎，診斷較困難且壞疽穿孔風險較高。"),
    TopicSeed("condition", "gallstone-ileus", "Gallstone ileus (膽石性腸阻塞)", ("gallstone ileus", "膽結石腸阻塞", "Rigler"), "膽腸瘻後膽石進入腸道造成機械性阻塞，常見於高齡膽石病人。"),
    TopicSeed("condition", "biliary-pancreatitis", "Biliary pancreatitis (膽源性胰臟炎)", ("biliary pancreatitis", "膽源性胰臟炎", "gallstone pancreatitis"), "膽石或膽泥阻塞壺腹可誘發急性胰臟炎，需評估 ERCP 與膽囊切除時機。"),
    TopicSeed("condition", "cholangiocarcinoma", "Cholangiocarcinoma (膽管癌)", ("Cholangiocarcinoma", "CCA", "膽管癌", "Klatskin"), "膽管上皮惡性腫瘤，可依肝內、肝門部與遠端膽管分類，常以阻塞性黃疸表現。"),
    TopicSeed("condition", "choledochal-cyst", "Choledochal cyst (膽道囊腫)", ("choledochal cyst", "膽道囊腫", "Todani"), "先天或後天膽道囊狀擴張，與膽管炎、胰臟炎、結石與膽道癌風險相關。"),
    TopicSeed("condition", "gallbladder-cancer", "Gallbladder cancer (膽囊癌)", ("gallbladder cancer", "膽囊癌", "gall bladder cancer"), "膽囊惡性腫瘤常與膽石、慢性發炎或 porcelain gallbladder 相關，早期症狀不明顯。"),
    TopicSeed("diagnostic", "mrcp", "Magnetic resonance cholangiopancreatography, MRCP (磁振膽胰管攝影)", ("MRCP", "核磁共振膽胰道", "magnetic resonance cholangiopancreatography"), "非侵襲性顯示膽道與胰管結構，用於膽總管結石、膽管癌、胰臟癌或胰膽管異常評估。"),
    TopicSeed("procedure", "percutaneous-cholecystostomy", "Percutaneous cholecystostomy (經皮膽囊引流)", ("percutaneous cholecystostomy", "經皮膽囊引流", "PTGBD"), "高風險急性膽囊炎病人可用經皮膽囊引流作為橋接或替代治療。"),
    # Pancreas surgery.
    TopicSeed("condition", "pancreatic-pseudocyst", "Pancreatic pseudocyst (胰臟假性囊腫)", ("pancreatic pseudocyst", "胰臟假性囊腫", "pseudocyst"), "急性或慢性胰臟炎後的液體囊腫，壁無上皮襯裡，需依症狀、感染、出血或阻塞決定引流。"),
    TopicSeed("condition", "pancreatic-necrosis", "Pancreatic necrosis (胰臟壞死)", ("pancreatic necrosis", "胰臟壞死", "infected necrosis"), "重症急性胰臟炎可有胰臟或周邊壞死，感染性壞死需抗生素與 step-up drainage/debridement 策略。"),
    TopicSeed("condition", "periampullary-cancer", "Periampullary cancer (壺腹周圍癌)", ("periampullary cancer", "壺腹周圍癌", "ampulla Vater cancer"), "壺腹周圍腫瘤包含胰頭癌、遠端膽管癌、十二指腸癌與壺腹癌，常以阻塞性黃疸表現。"),
    TopicSeed("condition", "pancreatic-neuroendocrine-tumor", "Pancreatic neuroendocrine tumor, pNET (胰臟神經內分泌腫瘤)", ("pancreatic neuroendocrine", "pNET", "胰臟神經內分泌腫瘤"), "胰臟 neuroendocrine tumor 可為功能性或非功能性，包含 insulinoma、gastrinoma、VIPoma、glucagonoma 等。"),
    TopicSeed("condition", "intraductal-papillary-mucinous-neoplasm", "Intraductal papillary mucinous neoplasm, IPMN (胰管內乳突黏液性腫瘤)", ("IPMN", "intraductal papillary mucinous", "胰管內乳突黏液"), "胰管系統黏液性囊腫性腫瘤，可依 main duct 或 branch duct 分型並有癌化風險。"),
    TopicSeed("condition", "mucinous-cystic-neoplasm-pancreas", "Mucinous cystic neoplasm of pancreas, MCN (胰臟黏液性囊性腫瘤)", ("mucinous cystic neoplasm", "MCN", "胰臟黏液性囊性腫瘤"), "多見於女性胰體尾部的 mucin-producing cystic neoplasm，具 ovarian-type stroma 與惡性潛能。"),
    TopicSeed("procedure", "pancreaticoduodenectomy", "Pancreaticoduodenectomy / Whipple procedure (胰十二指腸切除術)", ("Whipple procedure", "Whipple operation", "Whipple's resection", "pancreaticoduodenectomy", "胰十二指腸切除", "PPPD"), "胰頭癌、壺腹周圍癌或遠端膽管癌常見根治手術，需重建膽道、胰管與消化道。"),
    TopicSeed("procedure", "distal-pancreatectomy", "Distal pancreatectomy (遠端胰臟切除術)", ("distal pancreatectomy", "遠端胰臟切除", "胰體尾"), "胰體尾病灶可行遠端胰臟切除，常合併脾臟切除，需注意胰液滲漏與感染風險。"),
    TopicSeed("condition", "pancreatic-fistula", "Postoperative pancreatic fistula (術後胰瘻)", ("pancreatic fistula", "pancreatic leak", "胰液滲漏", "胰瘻"), "胰臟手術後胰液由引流管或傷口漏出，可造成膿瘍、出血、敗血與延長住院。"),
    # Breast surgery and pathology.
    TopicSeed("condition", "fibroadenoma", "Fibroadenoma (纖維腺瘤)", ("fibroadenoma", "纖維腺瘤"), "常見年輕女性良性乳房腫塊，通常界線清楚、可移動，需依影像與變化決定追蹤或切除。"),
    TopicSeed("condition", "fibrocystic-change", "Fibrocystic change (纖維囊性變化)", ("fibrocystic", "纖維囊性", "breast cyst"), "常見良性乳房變化，可有週期性疼痛、結節或囊腫，需與惡性徵象鑑別。"),
    TopicSeed("condition", "mastitis", "Mastitis (乳腺炎)", ("mastitis", "乳腺炎", "lactational mastitis"), "乳腺感染或發炎常見於哺乳期，可能進展為 breast abscess。"),
    TopicSeed("condition", "breast-abscess", "Breast abscess (乳房膿瘍)", ("breast abscess", "乳房膿瘍"), "乳腺感染局部化膿，常需抗生素與超音波導引抽吸或切開引流。"),
    TopicSeed("condition", "intraductal-papilloma", "Intraductal papilloma (乳管內乳突瘤)", ("intraductal papilloma", "乳管內乳突瘤", "nipple discharge"), "乳管內良性乳突狀病灶，可造成血性乳頭分泌物，需排除 atypia 或 malignancy。"),
    TopicSeed("condition", "phyllodes-tumor", "Phyllodes tumor (葉狀腫瘤)", ("phyllodes", "葉狀腫瘤", "cystosarcoma phyllodes"), "纖維上皮性乳房腫瘤，可為良性、邊緣性或惡性，治療重點是足夠切緣切除。"),
    TopicSeed("condition", "ductal-carcinoma-in-situ", "Ductal carcinoma in situ, DCIS (乳管原位癌)", ("DCIS", "ductal carcinoma in situ", "乳管原位癌", "comedo"), "非侵襲性乳管上皮惡性病灶，常以 mammography 微鈣化發現，治療依範圍與風險選擇切除、放療與內分泌治療。"),
    TopicSeed("condition", "lobular-carcinoma-in-situ", "Lobular carcinoma in situ, LCIS (小葉原位癌)", ("LCIS", "lobular carcinoma in situ", "葉狀原位癌", "E-cadherin"), "小葉上皮非侵襲性病灶，更多是雙側乳癌風險標記，常需風險管理與追蹤。"),
    TopicSeed("condition", "invasive-ductal-carcinoma", "Invasive ductal carcinoma (浸潤性乳管癌)", ("infiltrating ductal", "invasive ductal", "浸潤性乳腺管癌"), "最常見侵襲性乳癌組織型，治療依分期、ER/PR/HER2 與病人條件規劃。"),
    TopicSeed("condition", "invasive-lobular-carcinoma", "Invasive lobular carcinoma (浸潤性小葉癌)", ("infiltrating lobular", "invasive lobular", "浸潤性小葉癌"), "常呈瀰漫性生長且可能雙側或多中心，影像與觸診有時低估範圍。"),
    TopicSeed("condition", "paget-disease-of-breast", "Paget disease of breast (乳房 Paget disease)", ("Paget disease", "乳房 Paget", "eczematous eruption"), "乳頭乳暈濕疹樣病灶，常與 underlying DCIS 或 invasive breast cancer 相關，需切片確認。"),
    TopicSeed("diagnostic", "breast-ultrasonography", "Breast ultrasonography (乳房超音波)", ("breast ultrasonography", "乳房超音波", "breast ultrasound"), "評估乳房腫塊囊性或實質性，常用於年輕或緻密乳房，也可導引切片。"),
    TopicSeed("procedure", "core-needle-biopsy-breast", "Core needle biopsy of breast (乳房粗針切片)", ("core needle biopsy", "乳房粗針", "core biopsy"), "取得乳房病灶組織以判斷良惡性、受體狀態與治療方向。"),
    TopicSeed("procedure", "sentinel-lymph-node-biopsy", "Sentinel lymph node biopsy, SLNB (前哨淋巴結切片)", ("sentinel lymph node biopsy", "SLNB", "前哨淋巴結"), "乳癌腋下分期程序，可降低完整腋下廓清造成的淋巴水腫與神經肩部併發症。"),
    TopicSeed("procedure", "breast-conserving-surgery", "Breast-conserving surgery / lumpectomy (乳房保留手術)", ("lumpectomy", "breast-conserving", "partial mastectomy", "乳房保留"), "切除乳房腫瘤並保留多數乳房組織，常需搭配放射治療。"),
    TopicSeed("procedure", "axillary-lymph-node-dissection", "Axillary lymph node dissection, ALND (腋下淋巴結廓清)", ("axillary lymph node dissection", "ALND", "腋下淋巴結廓清"), "乳癌腋下淋巴結治療與分期手術，較 SLNB 有更高淋巴水腫與神經損傷風險。"),
)


TWELFTH_BOOK_SEEDS: tuple[TopicSeed, ...] = (
    # Thoracic wall, pleura, airway, and trauma.
    TopicSeed("condition", "pectus-excavatum", "Pectus excavatum (漏斗胸)", ("pectus excavatum", "漏斗胸", "funnel chest", "sunken chest"), "胸骨與肋軟骨向內凹陷的胸壁畸形，可造成外觀、心肺壓迫或運動耐受問題，嚴重度常以影像與功能評估。"),
    TopicSeed("condition", "pectus-carinatum", "Pectus carinatum (雞胸)", ("pectus carinatum", "雞胸", "pigeon chest"), "胸骨向外突出的胸壁畸形，治療依年齡、嚴重度與症狀選擇支架或手術。"),
    TopicSeed("condition", "poland-syndrome", "Poland syndrome (Poland 氏症候群)", ("Poland syndrome", "Poland 氏症候群", "胸大肌缺損"), "先天胸壁與上肢發育異常，典型包含單側胸大肌缺損，可合併乳房、肋骨或手部異常。"),
    TopicSeed("condition", "thoracic-outlet-syndrome", "Thoracic outlet syndrome (胸廓出口症候群)", ("thoracic outlet syndrome", "胸廓出口症候群", "TOS", "scalene triangle"), "臂神經叢、鎖骨下動靜脈在胸廓出口受壓造成神經、動脈或靜脈症狀。"),
    TopicSeed("condition", "chest-wall-tumor", "Chest wall tumor (胸壁腫瘤)", ("chest wall tumor", "胸壁腫瘤", "rib tumor", "sternal tumor"), "胸壁腫瘤可源自骨、軟骨、軟組織或轉移，評估重點是影像範圍、組織診斷與切除重建需求。"),
    TopicSeed("procedure", "nuss-procedure", "Nuss procedure (Nuss 漏斗胸矯正術)", ("Nuss procedure", "Nuss 漏斗胸", "minimally invasive repair of pectus excavatum"), "以胸骨後矯正鋼板頂起凹陷胸壁的微創漏斗胸手術，需注意心肺壓迫、鋼板移位與疼痛控制。"),
    TopicSeed("procedure", "ravitch-procedure", "Ravitch procedure (Ravitch 胸壁矯正術)", ("Ravitch procedure", "Ravitch 胸壁", "open repair of pectus"), "開放式胸壁矯正手術，常涉及異常肋軟骨切除與胸骨重塑。"),
    TopicSeed("condition", "malignant-pleural-effusion", "Malignant pleural effusion (惡性肋膜積液)", ("malignant pleural effusion", "惡性肋膜積水", "惡性肋膜積液", "MPE"), "惡性腫瘤侵犯或阻塞肋膜淋巴回流造成肋膜積液，處置需兼顧症狀緩解、肺復張能力與預後。"),
    TopicSeed("condition", "chylothorax", "Chylothorax (乳糜胸)", ("chylothorax", "乳糜胸", "chylous pleural effusion"), "胸管或淋巴系統受損使乳糜進入肋膜腔，肋膜液 triglyceride 升高，治療包含引流、營養調整與胸管處置。"),
    TopicSeed("condition", "mesothelioma", "Mesothelioma (惡性間皮瘤)", ("mesothelioma", "惡性間皮瘤", "malignant mesothelioma"), "肋膜間皮惡性腫瘤，常與 asbestos exposure 相關，可能以胸痛、肋膜積液與肋膜增厚表現。"),
    TopicSeed("procedure", "pleurodesis", "Pleurodesis (肋膜沾黏術)", ("pleurodesis", "肋膜沾黏", "talc pleurodesis"), "利用化學或機械刺激使臟層與壁層肋膜沾黏，常用於反覆氣胸或惡性肋膜積液症狀控制。"),
    TopicSeed("procedure", "decortication", "Decortication (剝皮術／纖維膜剝除術)", ("decortication", "纖維膜剝除", "pleural peel", "剝皮術"), "移除限制肺擴張的肋膜纖維皮，常用於 organized empyema 或 fibrothorax。"),
    TopicSeed("condition", "mediastinal-mass", "Mediastinal mass (縱隔腔腫塊)", ("mediastinal mass", "縱隔腔腫塊", "mediastinal tumor", "縱膈腔腫瘤"), "縱隔腔腫塊需依 anterior/middle/posterior mediastinum 分區鑑別，常見包含 thymoma、lymphoma、germ cell tumor 與神經源性腫瘤。"),
    TopicSeed("condition", "thymoma", "Thymoma (胸腺瘤)", ("thymoma", "胸腺瘤", "malignant thymoma"), "前縱隔腔常見腫瘤，可合併 myasthenia gravis、pure red cell aplasia 或 hypogammaglobulinemia。"),
    TopicSeed("condition", "mediastinal-germ-cell-tumor", "Mediastinal germ cell tumor (縱隔腔生殖細胞瘤)", ("mediastinal germ cell tumor", "縱隔腔生殖細胞瘤", "primary mediastinal germ cell"), "縱隔腔原發 germ cell tumor 多在前縱隔，需整合影像、AFP、beta-hCG 與組織診斷。"),
    TopicSeed("procedure", "tracheostomy", "Tracheostomy (氣管造口術)", ("tracheostomy", "tracheotomy", "氣管造口", "氣管造瘻"), "建立頸部氣管通道以維持長期呼吸道、協助呼吸器照護或繞過上呼吸道阻塞。"),
    TopicSeed("condition", "tracheal-tumor", "Tracheal tumor (氣管腫瘤)", ("tracheal tumor", "tracheal tumors", "氣管癌症", "氣管腫瘤"), "氣管原發腫瘤少見，可造成咳嗽、喘鳴、咳血或固定性氣道阻塞，需支氣管鏡與影像評估。"),
    TopicSeed("condition", "thoracic-trauma", "Thoracic trauma (胸部創傷)", ("thoracic trauma", "胸部創傷", "chest trauma"), "胸部創傷需依 ABC 評估呼吸道、通氣、循環與立即致命病灶，如張力性氣胸、開放性氣胸、大量血胸與連枷胸。"),
    TopicSeed("condition", "flail-chest", "Flail chest (連枷胸)", ("flail chest", "連枷胸", "paradoxical movement"), "多根相鄰肋骨多處骨折造成胸壁游離段與 paradoxical movement，可合併 pulmonary contusion 與呼吸衰竭。"),
    TopicSeed("condition", "open-pneumothorax", "Open pneumothorax (開放性氣胸)", ("open pneumothorax", "開放性氣胸", "sucking chest wound"), "胸壁開放傷使空氣經傷口進出肋膜腔，急救需封閉傷口並安排胸管與 definitive repair。"),
    TopicSeed("condition", "hemothorax", "Hemothorax (血胸)", ("hemothorax", "血胸", "massive hemothorax"), "血液積聚於肋膜腔，創傷後需評估失血量、胸管引流與開胸止血指徵。"),
    TopicSeed("condition", "tracheobronchial-injury", "Tracheobronchial injury (氣管支氣管損傷)", ("tracheobronchial injury", "氣管支氣管損傷", "bronchial rupture"), "嚴重胸部創傷可造成氣管或主支氣管斷裂，提示徵象包含持續漏氣、皮下氣腫與肺無法復張。"),
    TopicSeed("condition", "blunt-aortic-injury", "Blunt aortic injury (鈍傷性主動脈損傷)", ("blunt aortic injury", "blunt transection of aorta", "鈍傷性主動脈橫斷", "traumatic aortic injury"), "高速減速創傷可造成主動脈峽部損傷，需以影像快速診斷並控制血壓、評估 TEVAR 或手術。"),
    TopicSeed("condition", "neck-trauma", "Neck trauma (頸部創傷)", ("neck traumatic injury", "neck trauma", "頸部創傷", "zone II"), "頸部穿刺或鈍傷需依 zone、hard signs 與 airway/vascular/esophageal injury 風險決定探查或影像。"),
    # Esophageal surgical entities not already covered by GI seeds.
    TopicSeed("condition", "zenker-diverticulum", "Zenker diverticulum (Zenker 憩室)", ("Zenker diverticulum", "贊克氏憩室", "pharyngoesophageal diverticulum"), "咽食道交界的 pulsion diverticulum，可造成吞嚥困難、逆流、口臭與吸入風險。"),
    TopicSeed("condition", "caustic-esophageal-injury", "Caustic esophageal injury (腐蝕性食道傷害)", ("caustic burn", "caustic esophageal", "腐蝕性傷害", "腐蝕性食道"), "強酸或強鹼造成食道與胃灼傷，急性期需評估穿孔與內視鏡分級，慢性期注意狹窄與癌化風險。"),
    TopicSeed("condition", "esophageal-perforation", "Esophageal perforation (食道穿孔)", ("esophageal perforation", "食道破裂", "食道穿孔", "Boerhaave"), "食道全層破裂可造成縱隔炎、氣胸或敗血，早期診斷與引流/修補策略影響預後。"),
    TopicSeed("condition", "esophageal-foreign-body", "Esophageal foreign body (食道異物)", ("esophageal foreign body", "食道異物", "foreign body ingestion"), "異物或食物團卡在食道需依物品種類、位置、阻塞程度與穿孔風險決定內視鏡時機。"),
    TopicSeed("procedure", "esophagectomy", "Esophagectomy (食道切除術)", ("esophagectomy", "食道切除", "Ivor Lewis", "McKeown"), "食道癌或部分嚴重良性病變的外科切除，需搭配胃或腸道重建並注意吻合漏與肺部併發症。"),
    # Pediatric surgery.
    TopicSeed("condition", "branchial-cleft-remnant", "Branchial cleft remnant (腮裂遺跡)", ("branchial cleft", "腮裂遺跡", "branchial cleft remnant"), "胚胎腮裂殘留可形成頸部囊腫、竇道或瘻管，常位於胸鎖乳突肌前緣附近。"),
    TopicSeed("condition", "thyroglossal-duct-cyst", "Thyroglossal duct cyst (甲狀舌骨囊腫)", ("thyroglossal duct cyst", "甲狀舌骨囊腫", "Sistrunk"), "甲狀舌管殘留造成中線頸部囊腫，常隨吞嚥或伸舌移動，治療多為 Sistrunk procedure。"),
    TopicSeed("condition", "lymphangioma-cystic-hygroma", "Lymphangioma / cystic hygroma (淋巴管瘤／囊狀水瘤)", ("lymphangioma", "cystic hygroma", "淋巴管瘤", "囊狀水瘤"), "淋巴管發育異常造成頸部或腋下多房囊性腫塊，可能壓迫呼吸道或感染出血。"),
    TopicSeed("condition", "congenital-muscular-torticollis", "Congenital muscular torticollis (先天性肌性斜頸)", ("torticollis", "斜頸症", "congenital muscular torticollis"), "胸鎖乳突肌纖維化或腫塊造成頭頸姿勢偏斜，早期復健伸展多有效。"),
    TopicSeed("condition", "cystic-fibrosis", "Cystic fibrosis (囊性纖維化)", ("cystic fibrosis", "囊性纖維化", "CFTR"), "CFTR 異常造成黏稠分泌物、肺部感染、胰臟外分泌不足與胎便性腸阻塞等表現。"),
    TopicSeed("condition", "meconium-ileus", "Meconium ileus (胎便性腸阻塞)", ("meconium ileus", "胎便性腸阻塞", "meconium syndromes", "胎便症候群"), "黏稠胎便阻塞遠端迴腸，常與 cystic fibrosis 相關，需區分單純與複雜型。"),
    TopicSeed("condition", "intestinal-atresia", "Intestinal atresia (腸道閉鎖)", ("intestinal atresia", "腸道閉鎖", "bowel atresia"), "先天腸道管腔中斷造成新生兒腸阻塞，表現依閉鎖位置有膽汁性嘔吐、腹脹與胎便排出異常。"),
    TopicSeed("condition", "jejunoileal-atresia", "Jejunoileal atresia (空迴腸閉鎖)", ("jejunoileal atresia", "空迴腸閉鎖", "apple peel atresia"), "小腸遠端血管事件造成空腸或迴腸閉鎖，可有多發閉鎖或 apple-peel 型態。"),
    TopicSeed("condition", "necrotizing-enterocolitis", "Necrotizing enterocolitis (壞死性腸炎)", ("necrotizing enterocolitis", "壞死性腸炎", "pneumatosis intestinalis"), "早產兒腸道缺血、菌叢與餵食相關的發炎壞死疾病，影像可見 pneumatosis intestinalis，穿孔或壞死需手術。"),
    TopicSeed("condition", "imperforate-anus", "Imperforate anus (肛門閉鎖)", ("imperforate anus", "肛門閉鎖", "anorectal malformation", "肛門直腸畸形"), "肛門直腸發育異常，可分高位與低位並常合併泌尿生殖瘻管或 VACTERL 相關異常。"),
    TopicSeed("procedure", "pyloromyotomy", "Pyloromyotomy (幽門肌切開術)", ("pyloromyotomy", "Ramstedt pyloromyotomy", "Rammstedt pyloromyotomy", "幽門肌切開"), "肥厚性幽門狹窄的手術治療，術前需先矯正脫水、低氯與代謝性鹼中毒。"),
    TopicSeed("procedure", "ladd-procedure", "Ladd procedure (Ladd 手術)", ("Ladd procedure", "Ladd's procedure", "Ladd 手術"), "治療 intestinal malrotation/midgut volvulus 的手術，包含鬆解 Ladd bands、擴大腸繫膜基底、復位與 appendectomy。"),
    TopicSeed("procedure", "kasai-portoenterostomy", "Kasai portoenterostomy (Kasai 肝門腸吻合術)", ("Kasai", "portoenterostomy", "肝門腸吻合", "葛西手術"), "膽道閉鎖早期重建膽汁引流的手術，年齡越小成功率越高，失敗或進展肝硬化需肝移植。"),
    TopicSeed("condition", "prune-belly-syndrome", "Prune-belly syndrome (皺梅腹症候群)", ("prune-belly syndrome", "皺梅腹症候群", "Eagle-Barrett"), "腹壁肌肉缺損、泌尿道擴張與隱睪的先天症候群，可合併肺發育不良與腎功能問題。"),
    TopicSeed("condition", "inguinal-hernia", "Inguinal hernia (腹股溝疝氣)", ("inguinal hernia", "腹股溝疝氣", "indirect inguinal hernia"), "小兒腹股溝疝氣多因 processus vaginalis 未閉合，早產兒風險較高，需注意嵌頓。"),
    TopicSeed("condition", "hydrocele", "Hydrocele (陰囊水腫)", ("hydrocele", "陰囊水腫", "scrotal hydrocele"), "鞘狀突未閉或液體吸收異常造成陰囊積液，需區分 communicating 與 noncommunicating hydrocele。"),
    TopicSeed("condition", "cryptorchidism", "Cryptorchidism / undescended testis (隱睪症)", ("cryptorchidism", "undescended testis", "隱睪症", "UDT"), "睪丸未下降至陰囊，與不孕、睪丸癌與扭轉風險相關，需適時轉介與 orchiopexy。"),
    TopicSeed("condition", "retractile-testis", "Retractile testis (可縮回睪丸)", ("retractile testis", "retractile testes", "可縮回的睪丸"), "提睪肌反射使睪丸可上縮但能拉回陰囊，需與真正隱睪區分並追蹤是否 ascent。"),
    TopicSeed("condition", "testicular-torsion", "Testicular torsion (睪丸扭轉)", ("testicular torsion", "睪丸扭轉", "bell clapper"), "精索扭轉造成睪丸缺血，是急性陰囊痛外科急症，處置重點是及時 detorsion 與 orchiopexy。"),
    TopicSeed("condition", "hypospadias", "Hypospadias (尿道下裂)", ("hypospadias", "尿道下裂", "chordee"), "尿道口位於陰莖腹側，可合併陰莖彎曲，包皮常保留供修補使用。"),
    TopicSeed("procedure", "orchiopexy", "Orchiopexy (睪丸固定術)", ("orchiopexy", "orchidopexy", "睪丸固定術"), "將睪丸固定於陰囊，常用於 cryptorchidism 或 testicular torsion 後雙側固定。"),
    TopicSeed("procedure", "hypospadias-repair", "Hypospadias repair (尿道下裂修補術)", ("hypospadias repair", "尿道下裂修補", "urethroplasty"), "尿道下裂手術目標是矯正彎曲、重建尿道與改善外觀，手術時機與方法依位置和嚴重度決定。"),
    TopicSeed("condition", "rhabdomyosarcoma", "Rhabdomyosarcoma (橫紋肌肉瘤)", ("rhabdomyosarcoma", "橫紋肌肉瘤", "RMS"), "兒童常見軟組織肉瘤，可發生於頭頸、泌尿生殖道、四肢或軀幹，治療整合手術、化療與放療。"),
    TopicSeed("condition", "craniosynostosis", "Craniosynostosis (顱縫早閉)", ("craniosynostosis", "顱縫早閉", "sagittal synostosis"), "顱縫過早閉合造成頭形異常，可能影響腦部發育或顱內壓，需依縫線與嚴重度評估手術。"),
    TopicSeed("condition", "congenital-pulmonary-airway-malformation", "Congenital pulmonary airway malformation, CPAM (先天性肺呼吸道畸形)", ("congenital pulmonary airway malformation", "CPAM", "congenital cystic adenomatoid malformation", "CCAM"), "胎兒或新生兒肺部囊性發育異常，可造成呼吸窘迫、感染或縱隔偏移，治療依症狀與病灶規劃。"),
)


THIRTEENTH_BOOK_SEEDS: tuple[TopicSeed, ...] = (
    # Kidney, upper tract, and adrenal-facing urology.
    TopicSeed("condition", "renal-cyst", "Renal cyst (腎臟囊腫)", ("renal cyst", "腎臟囊腫", "renal cysts"), "腎臟常見結構異常，多數無症狀；影像有 septa、nodules 或 enhancement 時需依 Bosniak 分級評估惡性風險。"),
    TopicSeed("diagnostic", "bosniak-renal-cyst-classification", "Bosniak renal cyst classification (Bosniak 腎囊腫分級)", ("Bosniak", "Bosniak 分級", "Bosniak classification"), "依 CT/MRI 囊腫隔膜、鈣化、厚壁與顯影程度估計腎囊腫惡性風險並決定追蹤或切除。"),
    TopicSeed("condition", "renal-trauma", "Renal trauma (腎臟外傷)", ("renal trauma", "kidney trauma", "腎臟外傷", "shattered kidney"), "泌尿系統最常見外傷之一，依 AAST 分級、血流動力學與集尿系統/血管損傷決定保守、栓塞或手術。"),
    TopicSeed("condition", "renal-abscess", "Renal abscess (腎膿瘍)", ("renal abscess", "renal abscesses", "腎膿瘍", "perinephric abscess"), "嚴重腎臟或腎周感染液化形成膿瘍，糖尿病、阻塞、結石與洗腎病人風險較高，常需抗生素加影像導引引流。"),
    TopicSeed("condition", "emphysematous-pyelonephritis", "Emphysematous pyelonephritis (產氣性腎盂腎炎)", ("emphysematous pyelonephritis", "產氣性腎盂腎炎", "腎實質或腎周圍組織有氣體"), "壞死性產氣感染，常見於糖尿病或尿路阻塞，死亡率高，治療包含抗生素、控制血糖與解除阻塞/引流。"),
    TopicSeed("condition", "renal-cell-carcinoma", "Renal cell carcinoma, RCC (腎細胞癌)", ("renal cell carcinoma", "腎細胞癌", "RCC", "clear cell type RCC"), "成人最常見原發腎臟惡性腫瘤，可有血尿、腰痛、腫塊或 paraneoplastic syndrome；局部病灶以切除為主。"),
    TopicSeed("condition", "renal-oncocytoma", "Renal oncocytoma (腎嗜酸細胞瘤)", ("renal oncocytoma", "oncocytoma", "嗜酸細胞瘤"), "腎臟良性上皮腫瘤，但影像常難與 RCC 區分，通常需病理或切除後確認。"),
    TopicSeed("condition", "renal-angiomyolipoma", "Renal angiomyolipoma, AML (腎血管肌肉脂肪瘤)", ("angiomyolipoma", "腎血管肌肉脂肪瘤", "renal AML", "血管肌肉脂肪瘤"), "含血管、平滑肌與脂肪的腎臟良性腫瘤，可與 tuberous sclerosis 相關，病灶大或出血時需介入。"),
    TopicSeed("condition", "upper-tract-urothelial-carcinoma", "Upper tract urothelial carcinoma, UTUC (上泌尿道泌尿上皮癌)", ("upper tract urothelial carcinoma", "UTUC", "腎盂/輸尿管癌", "renal pelvic/ureteral tumor"), "腎盂或輸尿管的 urothelial carcinoma，常以血尿表現，標準治療多為 nephroureterectomy with bladder cuff excision。"),
    TopicSeed("procedure", "partial-nephrectomy", "Partial nephrectomy (部分腎切除術)", ("partial nephrectomy", "部分腎臟切除", "部份腎切除"), "保留腎功能的腎腫瘤手術，常用於小型 T1 renal mass，需依位置、大小與 R.E.N.A.L score 評估。"),
    TopicSeed("procedure", "radical-nephrectomy", "Radical nephrectomy (根除性腎切除術)", ("radical nephrectomy", "根除性腎臟全切除", "腎臟全切除"), "切除腎臟與 Gerota fascia 內容物的腎癌手術，適用於較大或不適合保腎的局部腎腫瘤。"),
    TopicSeed("procedure", "nephroureterectomy", "Nephroureterectomy with bladder cuff excision (腎輸尿管與膀胱袖口切除術)", ("nephroureterectomy", "bladder cuff", "腎盂/輸尿管/膀胱袖口全切除", "腎臟/輸尿管全切除"), "上泌尿道泌尿上皮癌標準手術，移除腎臟、輸尿管與膀胱袖口以降低殘端復發。"),
    # Congenital lower tract and trauma.
    TopicSeed("condition", "ureteral-duplication", "Ureteral duplication (雙套輸尿管)", ("duplication of ureter", "ureteral duplication", "雙套輸尿管", "Weigert-Meyer"), "輸尿管重複發育異常，可為 complete 或 incomplete duplication，常與 VUR、尿路感染或上腎段異常相關。"),
    TopicSeed("condition", "ureteropelvic-junction-obstruction", "Ureteropelvic junction obstruction, UPJO (輸尿管腎盂接合處阻塞)", ("ureteropelvic junction obstruction", "UPJO", "輸尿管腎盂接合處阻塞"), "腎盂輸尿管交界阻塞造成水腎，可產前發現或以腰腹痛、感染、結石表現，治療常為 pyeloplasty。"),
    TopicSeed("condition", "ectopic-ureter", "Ectopic ureter (輸尿管開口異位)", ("ectopic ureter", "輸尿管開口異位", "ureteral ectopia"), "輸尿管開口不在正常膀胱三角區，女性可有持續尿失禁，常合併 duplex system 或腎發育異常。"),
    TopicSeed("condition", "interstitial-cystitis", "Interstitial cystitis / bladder pain syndrome (間質性膀胱炎)", ("interstitial cystitis", "間質性膀胱炎", "bladder pain syndrome", "Hunner"), "慢性膀胱疼痛、頻尿與急尿症候群，尿檢通常無感染，膀胱鏡可見 glomerulation 或 Hunner lesion。"),
    TopicSeed("condition", "ureteral-injury", "Ureteral injury (輸尿管外傷)", ("ureteral injury", "輸尿管外傷", "輸尿管損傷", "ureteroureterostomy"), "輸尿管損傷常為醫源性或穿刺傷，診斷依 CT urography/顯影外漏，治療依位置與長度放置支架或重建。"),
    TopicSeed("condition", "bladder-trauma", "Bladder trauma (膀胱外傷)", ("bladder trauma", "膀胱外傷", "intraperitoneal rupture", "extraperitoneal rupture"), "膀胱破裂以 retrograde cystography 診斷，腹膜內破裂通常需手術，腹膜外破裂多以導尿管引流。"),
    TopicSeed("condition", "urethral-injury", "Urethral injury (尿道外傷)", ("urethral injury", "尿道外傷", "straddle injury", "membranous urethra"), "尿道損傷需注意尿道口出血、骨盆骨折與尿滯留，疑似時避免盲目導尿並先做 retrograde urethrography。"),
    TopicSeed("condition", "urethral-stricture", "Urethral stricture (尿道狹窄)", ("urethral stricture", "尿道狹窄", "urethrotomy"), "尿道纖維化狹窄造成尿流變細、排尿困難或感染，治療可為擴張、內切開或尿道重建。"),
    TopicSeed("condition", "phimosis", "Phimosis (包莖)", ("phimosis", "包莖", "preputial stenosis"), "包皮口狹窄無法退下，可為生理性或病理性，反覆感染、排尿問題或成人病理性包莖可考慮包皮環切。"),
    TopicSeed("condition", "paraphimosis", "Paraphimosis (嵌頓包莖)", ("paraphimosis", "嵌頓包莖"), "包皮退下後卡在龜頭冠狀溝造成水腫與缺血風險，是需立即復位的泌尿急症。"),
    # Urothelial, bladder, prostate, and male genital tumors.
    TopicSeed("condition", "bladder-cancer", "Bladder cancer / urothelial carcinoma (膀胱癌／泌尿上皮癌)", ("bladder cancer", "膀胱癌", "urothelial cell carcinoma", "transitional cell carcinoma"), "泌尿道常見惡性腫瘤，多為 urothelial carcinoma，典型以無痛性血尿表現，診斷與追蹤核心是 cystoscopy/TURBT。"),
    TopicSeed("condition", "bladder-carcinoma-in-situ", "Bladder carcinoma in situ, CIS (膀胱原位癌)", ("carcinoma in situ", "膀胱原位癌", "flat carcinoma in situ"), "膀胱高風險扁平原位病灶，進展風險高，常以 TURBT 後膀胱內 BCG 治療與密切追蹤。"),
    TopicSeed("procedure", "cystoscopy", "Cystoscopy (膀胱鏡)", ("cystoscopy", "膀胱鏡", "膀胱鏡檢"), "直接檢查膀胱與尿道，可用於血尿、膀胱癌診斷追蹤、結石與下泌尿道病灶評估。"),
    TopicSeed("procedure", "transurethral-resection-bladder-tumor", "Transurethral resection of bladder tumor, TURBT (經尿道膀胱腫瘤切除術)", ("TURBT", "transurethral resection of bladder tumor", "經尿道膀胱癌切除", "經尿道膀胱腫瘤切除"), "膀胱癌初始診斷、分期與治療程序，需取得肌層以判斷是否 muscle-invasive。"),
    TopicSeed("procedure", "radical-cystectomy", "Radical cystectomy (根除性膀胱切除術)", ("radical cystectomy", "根除性膀胱切除", "膀胱全切除"), "肌肉侵犯型膀胱癌或 BCG 失敗高風險病灶的標準手術，需合併尿路改道與骨盆腔器官切除考量。"),
    TopicSeed("drug", "intravesical-bcg", "Intravesical BCG (膀胱內 BCG 灌注)", ("intravesical BCG", "BCG 灌注", "膀胱內卡介苗", "膀胱內 BCG"), "以弱毒結核菌誘發局部免疫反應降低非肌肉侵犯型膀胱癌復發與進展風險。"),
    TopicSeed("condition", "prostatitis", "Prostatitis (攝護腺炎)", ("prostatitis", "攝護腺炎", "bacterial prostatitis"), "攝護腺感染或發炎可急性或慢性表現，常有下泌尿道症狀、會陰痛與 PSA 上升，急性尿滯留時避免經尿道導尿。"),
    TopicSeed("condition", "prostate-abscess", "Prostate abscess (攝護腺膿瘍)", ("prostate abscess", "攝護腺膿瘍"), "急性攝護腺炎治療不足或免疫低下病人可形成膿瘍，常需 TRUS/CT 評估與引流。"),
    TopicSeed("condition", "benign-prostatic-hyperplasia", "Benign prostatic hyperplasia, BPH (良性攝護腺增生)", ("benign prostatic hyperplasia", "BPH", "良性攝護腺增生", "良性前列腺肥大"), "攝護腺 transition zone 增生造成 LUTS 或 bladder outlet obstruction，治療依 IPSS、攝護腺大小與併發症決定。"),
    TopicSeed("condition", "prostate-cancer", "Prostate cancer (攝護腺癌)", ("prostate cancer", "攝護腺癌", "前列腺癌"), "男性常見癌症，多為 adenocarcinoma；風險分層依 PSA、Gleason score 與 TNM 分期決定觀察、手術、放療或 androgen deprivation therapy。"),
    TopicSeed("condition", "castration-resistant-prostate-cancer", "Castration-resistant prostate cancer, CRPC (去勢抗性攝護腺癌)", ("castration resistant", "castration-resistant", "hormone refractory", "睪丸切除阻抗性", "賀爾蒙難治性"), "攝護腺癌在去勢濃度 testosterone 下仍進展的狀態，需考慮第二代 androgen-axis 治療、化療、放射性核種或臨床試驗。"),
    TopicSeed("diagnostic", "prostate-specific-antigen", "Prostate-specific antigen, PSA (攝護腺特異抗原)", ("prostate-specific antigen", "PSA", "攝護腺特異抗原"), "攝護腺上皮分泌蛋白，受 BPH、prostatitis、導尿、DRE 與 5-alpha-reductase inhibitor 影響，用於風險評估與治療後追蹤。"),
    TopicSeed("diagnostic", "gleason-score", "Gleason score (Gleason 攝護腺癌分級)", ("Gleason score", "Gleason", "格里森"), "攝護腺癌病理分級系統，以主要與最高等級 pattern 加總，反映腫瘤侵襲性與治療風險分層。"),
    TopicSeed("diagnostic", "prostate-biopsy", "Prostate biopsy (攝護腺切片)", ("prostate biopsy", "TRUS biopsy", "攝護腺切片", "經直腸超音波切片"), "以系統性或標靶切片取得攝護腺組織確認癌症，常依 PSA、DRE 或影像異常決定。"),
    TopicSeed("procedure", "transurethral-resection-prostate", "Transurethral resection of prostate, TURP (經尿道攝護腺切除術)", ("TURP", "transurethral resection of prostate", "經尿道攝護腺切除", "經尿道前列腺刮除"), "BPH 常用手術治療，適合中等大小攝護腺；需注意出血、逆行性射精、尿失禁與 TUR syndrome。"),
    TopicSeed("procedure", "radical-prostatectomy", "Radical prostatectomy (根除性攝護腺切除術)", ("radical prostatectomy", "根除性攝護腺切除", "前列腺根除手術"), "局部攝護腺癌根治手術，切除攝護腺與儲精囊，可合併神經保留與骨盆淋巴結廓清。"),
    TopicSeed("procedure", "androgen-deprivation-therapy", "Androgen deprivation therapy, ADT (雄性素剝奪治療)", ("androgen deprivation therapy", "ADT", "雄性素阻斷", "complete androgen blockade", "adjuvant androgen deprivation therapy"), "透過 GnRH/LHRH 藥物、antiandrogen 或 orchiectomy 降低 androgen signaling，是轉移或高風險攝護腺癌重要治療。"),
    TopicSeed("drug", "alpha-1-blockers-urology", "Alpha-1 blockers for LUTS (泌尿用 alpha-1 阻斷劑)", ("α1A-blockers", "α1-blockers", "Tamsulosin", "Alfuzosin", "Silodosin", "Terazosin (Hytrin", "Doxazosin (Doxaben"), "放鬆膀胱頸、攝護腺與尿道平滑肌以改善 BPH/LUTS，但可能造成姿勢性低血壓或逆行性射精。"),
    TopicSeed("drug", "five-alpha-reductase-inhibitors", "5-alpha-reductase inhibitors (5-alpha 還原酶抑制劑)", ("5α-reductase inhibitors", "5-alpha reductase inhibitor", "Finasteride", "Dutasteride", "5α 還原酶抑制"), "阻斷 testosterone 轉為 DHT，使攝護腺縮小並降低 BPH 進展；會使 PSA 約下降一半。"),
    TopicSeed("drug", "lhrh-gnrh-agonists", "LHRH/GnRH agonists (LHRH/GnRH 促進劑)", ("LHRH agonist", "GnRH agonists", "Leuprolide", "Goserelin", "Triptorelin", "Histrelin"), "長期下調 pituitary GnRH receptor 以降低 LH/testosterone，是 ADT 常用藥物，初期有 testosterone flare。"),
    TopicSeed("drug", "androgen-receptor-antagonists", "Androgen receptor antagonists (雄性素受器拮抗劑)", ("androgen receptor antagonist", "Flutamide", "Bicalutamide", "Nilutamide", "雄性素受器拮抗劑"), "阻斷 androgen receptor 訊號，可與 LHRH agonist 合併作 complete androgen blockade。"),
    # Stones, lower tract function, and procedures.
    TopicSeed("condition", "staghorn-calculus", "Staghorn calculus (鹿角結石)", ("staghorn calculus", "staghorn calculi", "鹿角結石"), "沿腎盂腎盞生長的大型分枝結石，常與 struvite/infection stone 相關，通常需 PCNL 等介入清除。"),
    TopicSeed("condition", "struvite-stone", "Struvite stone (磷酸胺鎂感染性結石)", ("struvite", "磷酸胺鎂", "infection stone", "感染性結石"), "urease-producing bacteria 使尿液鹼化形成 magnesium ammonium phosphate stone，可長成鹿角結石。"),
    TopicSeed("condition", "uric-acid-stone", "Uric acid stone (尿酸結石)", ("uric acid stone", "尿酸結石", "radiolucent stone"), "酸性尿液與高尿酸尿相關的 radiolucent stone，治療重點包含尿液鹼化與降低尿酸負荷。"),
    TopicSeed("condition", "cystine-stone", "Cystine stone (胱氨酸結石)", ("cystine stone", "胱氨酸結石", "cystinuria"), "cystinuria 造成的遺傳性結石，常需大量飲水、尿液鹼化與 thiol-binding drugs。"),
    TopicSeed("procedure", "extracorporeal-shock-wave-lithotripsy", "Extracorporeal shock wave lithotripsy, ESWL (體外震波碎石術)", ("extracorporeal shock wave lithotripsy", "ESWL", "體外震波碎石"), "以體外震波碎石，常用於較小腎結石或輸尿管結石；懷孕、出血傾向、完全阻塞等為重要禁忌。"),
    TopicSeed("procedure", "percutaneous-nephrolithotomy", "Percutaneous nephrolithotomy, PCNL (經皮腎造口取石術)", ("percutaneous nephrolithotomy", "PCNL", "經皮腎造口取石", "經皮穿腎取石"), "大型腎結石或鹿角結石常用取石術，經皮腎通道進入腎盂腎盞碎石並取出。"),
    TopicSeed("procedure", "ureteroscopic-lithotripsy", "Ureteroscopic lithotripsy (輸尿管鏡碎石術)", ("ureteroscopic lithotripsy", "ureteroscopic stone extraction", "輸尿管鏡碎石", "輸尿管鏡取石"), "以輸尿管鏡進入輸尿管或腎盂進行雷射/氣動碎石，常用於較大或 ESWL 不適合的輸尿管結石。"),
    TopicSeed("procedure", "percutaneous-nephrostomy", "Percutaneous nephrostomy, PCN (經皮腎造口引流)", ("percutaneous nephrostomy", "PCN tube", "經皮腎造口", "經皮穿腎引流"), "經皮置管引流腎盂，可用於感染性阻塞、腎積水、尿液外漏或特定介入通道。"),
    TopicSeed("procedure", "ureteral-stent", "Ureteral stent / double-J stent (輸尿管支架／雙 J 導管)", ("double-J", "double J", "ureteral stent", "雙 J 導管", "輸尿管支架"), "跨越輸尿管阻塞或修補處維持尿流，常用於結石、輸尿管損傷或手術後引流。"),
    TopicSeed("diagnostic", "urodynamic-study", "Urodynamic study (尿路動力學檢查)", ("urodynamic", "urodynamics", "尿路動力學", "尿路動態攝影"), "評估下泌尿道儲尿與排尿功能的檢查群，包含 uroflowmetry、cystometry、pressure-flow study 與 sphincter EMG。"),
    TopicSeed("diagnostic", "uroflowmetry", "Uroflowmetry (尿流速測定)", ("uroflowmetry", "urinary flow rate", "尿流速圖", "最大尿流速"), "量測尿流曲線與 maximum flow rate，用於初步評估 obstruction 或 detrusor underactivity。"),
    TopicSeed("diagnostic", "cystometry", "Cystometry / cystometrogram, CMG (膀胱壓力圖)", ("cystometry", "cystometrogram", "CMG", "膀胱壓力圖"), "灌注膀胱並量測 Pves/Pabd/Pdet、容量、感覺與順應性，是尿路動力學核心項目。"),
    TopicSeed("diagnostic", "urethral-pressure-profile", "Urethral pressure profile (尿道壓力分佈圖)", ("urethral pressure profile", "pressure profile measurement", "尿道壓力分佈圖"), "以導管量測尿道不同位置壓力，評估括約肌閉鎖壓力與功能性尿道長度。"),
    TopicSeed("condition", "urinary-incontinence", "Urinary incontinence (尿失禁)", ("urinary incontinence", "尿失禁"), "非自願漏尿症候群，需區分 stress、urge、overflow、mixed 與 neurogenic etiologies。"),
    TopicSeed("condition", "stress-urinary-incontinence", "Stress urinary incontinence (應力性尿失禁)", ("stress urinary incontinence", "應力性尿失禁", "Marshall-Marchetti-Krantz"), "咳嗽、運動或腹壓上升時漏尿，多與骨盆底支持不足或括約肌功能相關。"),
    TopicSeed("condition", "urge-incontinence", "Urge incontinence (急迫性尿失禁)", ("urge incontinence", "急迫性尿失禁", "detrusor instability"), "強烈尿急後來不及如廁而漏尿，常與 detrusor overactivity 或神經疾病相關。"),
    TopicSeed("condition", "overflow-incontinence", "Overflow incontinence (滿脹性尿失禁)", ("overflow incontinence", "滿脹性尿失禁"), "膀胱過度充盈後尿液溢出，可由 bladder outlet obstruction 或 detrusor underactivity 造成。"),
    TopicSeed("condition", "neurogenic-bladder", "Neurogenic bladder (神經異常膀胱)", ("neurogenic bladder", "neuropathic bladder", "神經異常膀胱", "NGB"), "神經病灶造成膀胱儲尿或排尿功能異常，治療目標是低壓儲尿、有效排空與保護腎功能。"),
    TopicSeed("condition", "detrusor-sphincter-dyssynergia", "Detrusor-sphincter dyssynergia, DSD (逼尿肌括約肌共濟失調)", ("detrusor-sphincter", "detrusor sphincter dyssynergia", "DSD", "逼尿肌括約肌共濟"), "逼尿肌收縮時外括約肌無法放鬆，常見於薦髓以上病灶，可造成高壓排尿與上泌尿道傷害。"),
    TopicSeed("condition", "overactive-bladder", "Overactive bladder (膀胱過動症)", ("overactive bladder", "膀胱過動", "detrusor overactivity"), "以尿急、頻尿、夜尿可合併急迫性尿失禁為核心，治療包含行為、antimuscarinic、beta-3 agonist 與 botulinum toxin。"),
    TopicSeed("condition", "autonomic-dysreflexia", "Autonomic dysreflexia (自主神經反射異常)", ("autonomic dysreflexia", "自主神經反射異常"), "高位脊髓損傷病人因膀胱、腸道或疼痛刺激引發突發高血壓、頭痛、潮紅與反射性心搏變化。"),
    TopicSeed("condition", "nocturnal-enuresis", "Nocturnal enuresis (夜尿／尿床)", ("nocturnal enuresis", "尿床", "夜間多尿症"), "兒童睡眠中不自主排尿，需區分 primary/secondary enuresis 並評估 UTI、便秘、睡眠與膀胱容量。"),
    TopicSeed("drug", "antimuscarinic-bladder-drugs", "Antimuscarinic bladder drugs (膀胱抗膽鹼藥)", ("Oxybutynin", "Tolterodine", "Trospium", "Solifenacin", "Darifenacin", "抗膽鹼", "antimuscarinics"), "抑制逼尿肌不自主收縮，用於 overactive bladder、urge incontinence 或 neurogenic overactive bladder。"),
    # Andrology and male infertility.
    TopicSeed("condition", "erectile-dysfunction", "Erectile dysfunction (勃起功能障礙)", ("erectile dysfunction", "勃起功能異常", "勃起功能障礙", "impotence"), "無法達到或維持足夠勃起以完成滿意性行為，需評估 vascular、neurogenic、hormonal、psychogenic 與 drug-induced causes。"),
    TopicSeed("condition", "premature-ejaculation", "Premature ejaculation (早發性射精／早洩)", ("premature ejaculation", "rapid ejaculation", "早發性射精", "早洩"), "射精控制不足造成過早射精與困擾，定義可依陰道內射精潛伏時間、控制感與伴侶滿意度。"),
    TopicSeed("condition", "retrograde-ejaculation", "Retrograde ejaculation (逆行性射精)", ("retrograde ejaculation", "逆行性射精"), "射精時精液逆流入膀胱，常見於膀胱頸功能異常、糖尿病自律神經病變、alpha-blocker 或攝護腺手術後。"),
    TopicSeed("condition", "male-infertility", "Male infertility (男性不孕症)", ("male infertility", "男性不孕症", "男性不孕"), "男性因素造成不孕需整合病史、身體檢查、精液分析、荷爾蒙與遺傳/阻塞性評估。"),
    TopicSeed("condition", "varicocele", "Varicocele (精索靜脈曲張)", ("varicocele", "精索靜脈曲張"), "蔓狀靜脈叢擴張，左側常見，是男性不孕最常見可手術矯正因素之一。"),
    TopicSeed("diagnostic", "semen-analysis", "Semen analysis (精液分析)", ("semen analysis", "精液分析", "精蟲濃度", "sperm/ml"), "男性不孕第一線檢查，評估精液量、精蟲濃度、活動力、前進度與型態。"),
    TopicSeed("diagnostic", "nocturnal-penile-tumescence-test", "Nocturnal penile tumescence test, NPT (夜間陰莖勃起監測)", ("nocturnal penile tumescence", "NPT test", "夜間陰莖勃起", "Snap-Gauge"), "評估睡眠中自然勃起以區分 psychogenic 與 organic erectile dysfunction。"),
    TopicSeed("drug", "pde5-inhibitors", "PDE5 inhibitors (第五型磷酸二酯酶抑制劑)", ("PDE5 inhibitors", "Phosphodiesterase", "Sildenafil", "Viagra", "Tadalafil", "Cialis", "Vardenafil", "Levitra"), "增強 NO-cGMP 路徑改善勃起功能，與 nitrates 合用可造成危險低血壓。"),
    TopicSeed("procedure", "penile-prosthesis", "Penile prosthesis (人工陰莖植入)", ("penile prosthesis", "人工陰莖", "陰莖血管支架"), "嚴重或藥物無效 erectile dysfunction 的手術選項，可為半硬式或充氣式植入物。"),
    TopicSeed("procedure", "varicocelectomy", "Varicocelectomy (精索靜脈曲張手術)", ("varicocelectomy", "精索靜脈曲張切除", "精索靜脈曲張手術"), "治療有症狀或不孕相關 varicocele 的手術，目標是阻斷逆流靜脈並保留動脈與淋巴。"),
    TopicSeed("procedure", "vasovasostomy", "Vasovasostomy (輸精管吻合術)", ("vasovasostomy", "輸精管吻合術"), "輸精管阻塞或結紮後重建生殖道連續性的顯微手術。"),
    TopicSeed("procedure", "testicular-sperm-extraction", "Testicular sperm extraction, TESE (睪丸取精術)", ("testicular sperm extraction", "TESE", "睪丸取精術", "MESA"), "無精症或阻塞性男性不孕可直接由睪丸或副睪取得精子供人工生殖使用。"),
    TopicSeed("physiology", "male-reproductive-endocrine-axis", "Male reproductive endocrine axis (男性生殖內分泌軸)", ("LH", "FSH", "Leydig", "Sertoli", "male reproductive endocrine", "睪丸生理"), "GnRH-LH/FSH-testosterone 軸調控 Leydig cell testosterone 與 Sertoli cell spermatogenesis。"),
    TopicSeed("anatomy", "prostate-zones", "Prostate zones (攝護腺分區)", ("prostate zone", "peripheral zone", "transition zone", "central zone", "攝護腺分區"), "攝護腺周邊區常發生 prostate cancer，transition zone 常發生 BPH，分區影響 DRE、TRUS 與切片策略。"),
    TopicSeed("physiology", "lower-urinary-tract-function", "Lower urinary tract function (下泌尿道儲尿與排尿功能)", ("lower urinary tract function", "下泌尿道功能", "guarding reflex", "pontine micturition"), "膀胱、尿道括約肌、交感/副交感/體神經與橋腦排尿中樞協調儲尿與排尿。"),
    TopicSeed("condition", "adrenal-androgen-excess", "Adrenal androgen excess (腎上腺雄性素過多)", ("adrenal androgen", "腎上腺雄性素症", "adrenal androgenic syndromes"), "腎上腺網狀帶增生或皮質腫瘤分泌過多 androgen，可造成男性化、性早熟或女性 virilization。"),
)


ALL_SEEDS: tuple[TopicSeed, ...] = SEEDS + SECOND_BOOK_SEEDS + THIRD_BOOK_SEEDS + FOURTH_BOOK_SEEDS + FIFTH_BOOK_SEEDS + SIXTH_BOOK_SEEDS + SEVENTH_BOOK_SEEDS + EIGHTH_BOOK_SEEDS + NINTH_BOOK_SEEDS + TENTH_BOOK_SEEDS + ELEVENTH_BOOK_SEEDS + TWELFTH_BOOK_SEEDS + THIRTEENTH_BOOK_SEEDS


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


def chapter_sort_key(path: Path) -> tuple[int, int, str]:
    stem_order = {
        "甲": 1,
        "乙": 2,
        "丙": 3,
        "丁": 4,
        "戊": 5,
        "己": 6,
        "庚": 7,
        "辛": 8,
        "壬": 9,
        "癸": 10,
        "子": 11,
        "丑": 12,
        "寅": 13,
        "卯": 14,
        "辰": 15,
        "巳": 16,
        "午": 17,
        "未": 18,
        "申": 19,
        "酉": 20,
        "戌": 21,
        "亥": 22,
    }
    part_order = {"第一篇": 1, "第二篇": 2, "第三篇": 3, "第四篇": 4, "第五篇": 5, "第六篇": 6}
    part = 99
    for label, order in part_order.items():
        if label in path.stem:
            part = order
            break
    match = re.search(r"_([甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥])、", path.stem)
    stem = stem_order.get(match.group(1), 99) if match else 99
    return (part, stem, path.name)


def chapter_files(book_dir: Path) -> list[Path]:
    full_book = book_dir / f"{book_dir.name}.md"
    files = sorted(book_dir.glob("*.md"), key=chapter_sort_key)
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


def existing_topic_parts(path: Path, replace_source_prefix: str | None = None) -> tuple[list[str], list[str], str]:
    if not path.exists():
        return [], [], TODAY
    text = path.read_text(encoding="utf-8", errors="ignore")
    sources_section = ""
    match_sources = re.search(r"## Source Coverage\n\n(.*?)(?=\n## Key Details From Sources)", text, flags=re.S)
    if match_sources:
        sources_section = match_sources.group(1)
    raw_sources = re.findall(r"\[\[(sources/[^\]|#]+)(?:[^\]]*)\]\]", sources_section)
    if replace_source_prefix:
        raw_sources = [source for source in raw_sources if not source.startswith(f"sources/{replace_source_prefix}")]
    sources = [f"[[{source}]]" for source in dict.fromkeys(raw_sources)]
    details: list[str] = []
    match = re.search(r"## Key Details From Sources\n\n(.*?)(?=\n## Clinical Caveats)", text, flags=re.S)
    if match:
        for line in match.group(1).splitlines():
            if line.startswith("- "):
                if replace_source_prefix and f"[[sources/{replace_source_prefix}" in line:
                    continue
                details.append(line)
    created_match = re.search(r"^created:\s*([0-9-]+)", text, flags=re.M)
    created = created_match.group(1) if created_match else TODAY
    return sources, details, created


def topic_page(seed: TopicSeed, source_mentions: list[tuple[str, Path, list[str]]], available_slugs: set[str], book_name: str, book_key: str) -> str:
    path = seed_page_path(seed)
    prior_sources, prior_details, created = existing_topic_parts(path, replace_source_prefix=book_key)
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
        "cyanotic-congenital-heart-disease": ["tetralogy-of-fallot", "pulmonary-atresia", "tricuspid-atresia", "transposition-of-great-arteries", "hypoplastic-left-heart-syndrome", "prostaglandin-e1"],
        "acyanotic-congenital-heart-disease": ["ventricular-septal-defect", "atrial-septal-defect", "patent-ductus-arteriosus", "pulmonary-valve-stenosis", "coarctation-of-aorta", "echocardiography"],
        "tetralogy-of-fallot": ["hypercyanotic-spell", "cyanotic-congenital-heart-disease", "prostaglandin-e1"],
        "transposition-of-great-arteries": ["balloon-atrial-septostomy", "arterial-switch-operation", "prostaglandin-e1", "cyanotic-congenital-heart-disease"],
        "patent-ductus-arteriosus": ["prostaglandin-e1", "indomethacin", "echocardiography"],
        "pediatric-dehydration": ["oral-rehydration-therapy", "diarrhea", "infectious-gastroenteritis"],
        "biliary-atresia": ["jaundice", "liver-function-tests"],
        "vesicoureteral-reflux": ["urinary-tract-infection", "urinalysis"],
        "post-streptococcal-glomerulonephritis": ["glomerulonephritis", "nephritic-syndrome", "complement-system"],
        "bronchiolitis": ["palivizumab", "oxygen-therapy"],
        "measles": ["pediatric-immunization-schedule"],
        "rubella": ["pediatric-immunization-schedule", "congenital-rubella-syndrome"],
        "primary-immunodeficiency": ["severe-combined-immunodeficiency", "x-linked-agammaglobulinemia", "selective-iga-deficiency", "chronic-granulomatous-disease", "wiskott-aldrich-syndrome"],
        "severe-combined-immunodeficiency": ["primary-immunodeficiency", "vaccine-contraindications"],
        "attention-deficit-hyperactivity-disorder": ["developmental-milestones"],
        "febrile-seizure": ["acute-bacterial-meningitis"],
        "precocious-puberty": ["bone-age", "tanner-staging", "growth-chart"],
        "short-stature": ["bone-age", "growth-chart", "turner-syndrome"],
        "newborn-screening": ["congenital-hypothyroidism", "phenylketonuria", "galactosemia", "methylmalonic-acidemia", "congenital-adrenal-hyperplasia"],
        "inborn-errors-of-metabolism": ["newborn-screening", "phenylketonuria", "galactosemia", "methylmalonic-acidemia", "glycogen-storage-disease", "mitochondrial-disease"],
        "down-syndrome": ["duodenal-atresia", "congenital-hypothyroidism", "acute-lymphoblastic-leukemia"],
        "digeorge-syndrome": ["conotruncal-heart-disease", "hypoparathyroidism", "primary-immunodeficiency"],
        "torch-infections": ["congenital-cmv-infection", "congenital-toxoplasmosis", "congenital-rubella-syndrome", "neonatal-herpes"],
        "neonatal-respiratory-distress-syndrome": ["surfactant-therapy", "apgar-score", "oxygenation-and-ventilation"],
        "neonatal-jaundice": ["phototherapy", "exchange-transfusion", "bilirubin-metabolism"],
        "wilms-tumor": ["kidney", "tumor-staging"],
        "neuroblastoma": ["adrenal-gland", "tumor-markers"],
        "retinoblastoma": ["genetic-counseling"],
        "skin": ["epidermis", "dermis", "skin-appendages", "skin-barrier-function", "primary-skin-lesions"],
        "epidermis": ["skin-barrier-function", "pemphigus-vulgaris", "staphylococcal-scalded-skin-syndrome", "nikolsky-sign"],
        "primary-skin-lesions": ["secondary-skin-lesions", "nikolsky-sign"],
        "staphylococcal-scalded-skin-syndrome": ["impetigo", "staphylococcus-aureus-infection", "nikolsky-sign", "penicillins", "cephalosporins"],
        "toxic-shock-syndrome": ["staphylococcus-aureus-infection", "streptococcus-pyogenes-infection", "clindamycin", "vancomycin"],
        "impetigo": ["ecthyma", "staphylococcus-aureus-infection", "streptococcus-pyogenes-infection"],
        "herpes-zoster": ["varicella-zoster-virus-infection", "acyclovir"],
        "dermatophytosis": ["koh-preparation", "wood-lamp-examination"],
        "pityriasis-versicolor": ["koh-preparation", "wood-lamp-examination"],
        "pemphigus-vulgaris": ["bullous-pemphigoid", "nikolsky-sign", "systemic-corticosteroids", "immunosuppressants"],
        "bullous-pemphigoid": ["pemphigus-vulgaris", "linear-iga-bullous-dermatosis", "systemic-corticosteroids"],
        "dermatitis-herpetiformis": ["celiac-disease"],
        "contact-dermatitis": ["patch-test", "atopic-dermatitis"],
        "atopic-dermatitis": ["skin-barrier-function", "contact-dermatitis", "seborrheic-dermatitis"],
        "psoriasis": ["psoriatic-arthritis", "methotrexate", "biologic-dmards", "tnf-inhibitors"],
        "vitiligo": ["autoimmune-thyroid-disease", "thyroid-function-tests"],
        "melanocytic-nevus": ["melanoma"],
        "actinic-keratosis": ["squamous-cell-carcinoma-skin"],
        "melanoma": ["melanocytic-nevus", "tumor-staging"],
        "basal-cell-carcinoma": ["actinic-keratosis", "squamous-cell-carcinoma-skin"],
        "squamous-cell-carcinoma-skin": ["actinic-keratosis", "bowen-disease"],
        "mycosis-fungoides": ["lymphoma"],
        "peutz-jeghers-syndrome": ["melanocytic-nevus"],
        "ichthyosis-vulgaris": ["skin-barrier-function", "atopic-dermatitis"],
        "schizophrenia": ["psychosis", "antipsychotics", "electroconvulsive-therapy", "schizoaffective-disorder", "schizophreniform-disorder", "brief-psychotic-disorder"],
        "psychosis": ["schizophrenia", "delusional-disorder", "amphetamine-induced-psychotic-disorder", "antipsychotics"],
        "major-depressive-disorder": ["antidepressants", "selective-serotonin-reuptake-inhibitors", "electroconvulsive-therapy", "suicidal-behavior", "persistent-depressive-disorder", "pseudodementia"],
        "bipolar-disorder": ["bipolar-i-disorder", "bipolar-ii-disorder", "lithium", "valproate", "carbamazepine", "antipsychotics", "electroconvulsive-therapy"],
        "bipolar-i-disorder": ["bipolar-disorder", "lithium", "valproate", "antipsychotics"],
        "bipolar-ii-disorder": ["bipolar-disorder", "persistent-depressive-disorder"],
        "persistent-depressive-disorder": ["major-depressive-disorder", "double-depression", "antidepressants"],
        "panic-disorder": ["agoraphobia", "selective-serotonin-reuptake-inhibitors", "benzodiazepines", "cognitive-behavioral-therapy"],
        "obsessive-compulsive-disorder": ["selective-serotonin-reuptake-inhibitors", "cognitive-behavioral-therapy"],
        "specific-phobia": ["cognitive-behavioral-therapy", "beta-blockers"],
        "social-anxiety-disorder": ["selective-serotonin-reuptake-inhibitors", "beta-blockers", "cognitive-behavioral-therapy"],
        "generalized-anxiety-disorder": ["selective-serotonin-reuptake-inhibitors", "benzodiazepines", "cognitive-behavioral-therapy"],
        "posttraumatic-stress-disorder": ["selective-serotonin-reuptake-inhibitors", "cognitive-behavioral-therapy"],
        "somatic-symptom-disorder": ["illness-anxiety-disorder", "psychotherapy"],
        "conversion-disorder": ["mental-status-examination", "psychotherapy"],
        "anorexia-nervosa": ["major-depressive-disorder", "electrolyte-disorders", "psychotherapy"],
        "sleep-disorders": ["benzodiazepines", "obstructive-sleep-apnea"],
        "personality-disorders": ["suicidal-behavior", "nonsuicidal-self-injury", "psychotherapy"],
        "substance-use-disorder": ["alcohol-use-disorder", "amphetamine-intoxication", "opioid-intoxication", "benzodiazepines"],
        "alcohol-use-disorder": ["alcohol-intoxication", "alcohol-withdrawal-syndrome", "wernicke-korsakoff-syndrome", "liver-cirrhosis"],
        "alcohol-withdrawal-syndrome": ["benzodiazepines", "delirium"],
        "wernicke-korsakoff-syndrome": ["alcohol-use-disorder", "thiamine"],
        "amphetamine-intoxication": ["amphetamine-withdrawal", "amphetamine-induced-psychotic-disorder", "psychosis"],
        "opioid-intoxication": ["opioid-withdrawal", "substance-use-disorder", "respiratory-failure"],
        "dementia": ["alzheimer-disease", "vascular-dementia", "pseudodementia", "delirium", "mini-mental-state-examination"],
        "alzheimer-disease": ["dementia"],
        "vascular-dementia": ["dementia", "stroke", "hypertension"],
        "pseudodementia": ["major-depressive-disorder", "dementia"],
        "delirium": ["dementia", "mental-status-examination", "antipsychotics"],
        "attention-deficit-hyperactivity-disorder": ["methylphenidate", "autism-spectrum-disorder", "tic-disorder"],
        "autism-spectrum-disorder": ["attention-deficit-hyperactivity-disorder", "intellectual-disability", "fragile-x-syndrome"],
        "tic-disorder": ["tourette-syndrome", "attention-deficit-hyperactivity-disorder"],
        "tourette-syndrome": ["tic-disorder", "attention-deficit-hyperactivity-disorder", "antipsychotics"],
        "intellectual-disability": ["autism-spectrum-disorder", "down-syndrome", "fragile-x-syndrome"],
        "suicidal-behavior": ["suicide-risk-assessment", "major-depressive-disorder", "bipolar-disorder", "substance-use-disorder", "nonsuicidal-self-injury"],
        "nonsuicidal-self-injury": ["suicidal-behavior", "personality-disorders"],
        "antipsychotics": ["schizophrenia", "bipolar-disorder", "extrapyramidal-symptoms", "neuroleptic-malignant-syndrome", "metabolic-syndrome"],
        "extrapyramidal-symptoms": ["antipsychotics"],
        "neuroleptic-malignant-syndrome": ["antipsychotics", "rhabdomyolysis"],
        "antidepressants": ["major-depressive-disorder", "selective-serotonin-reuptake-inhibitors", "tricyclic-antidepressants", "monoamine-oxidase-inhibitors", "monoamine-hypothesis"],
        "selective-serotonin-reuptake-inhibitors": ["antidepressants", "major-depressive-disorder", "obsessive-compulsive-disorder", "panic-disorder"],
        "benzodiazepines": ["panic-disorder", "generalized-anxiety-disorder", "alcohol-withdrawal-syndrome", "substance-use-disorder"],
        "lithium": ["bipolar-disorder", "thyroid-function-tests", "kidney"],
        "valproate": ["bipolar-disorder", "liver-function-tests"],
        "carbamazepine": ["bipolar-disorder", "stevens-johnson-syndrome-toxic-epidermal-necrolysis"],
        "methylphenidate": ["attention-deficit-hyperactivity-disorder"],
        "electroconvulsive-therapy": ["major-depressive-disorder", "bipolar-disorder", "schizophrenia"],
        "psychotherapy": ["cognitive-behavioral-therapy", "somatic-symptom-disorder", "personality-disorders"],
        "cognitive-behavioral-therapy": ["psychotherapy", "panic-disorder", "obsessive-compulsive-disorder", "posttraumatic-stress-disorder"],
        "central-nervous-system": ["brainstem", "spinal-cord", "cranial-nerves", "cerebrospinal-fluid-analysis"],
        "cranial-nerves": ["cranial-nerve-palsy", "brainstem", "neurologic-examination"],
        "basal-ganglia": ["parkinson-disease", "huntington-disease", "wilson-disease", "extrapyramidal-symptoms"],
        "cerebellum": ["neurologic-examination", "brain-magnetic-resonance-imaging"],
        "brainstem": ["cranial-nerves", "stroke", "central-pontine-myelinolysis"],
        "spinal-cord": ["corticospinal-tract", "multiple-sclerosis", "neuromyelitis-optica", "subacute-combined-degeneration"],
        "peripheral-nerves": ["polyneuropathy", "diabetic-neuropathy", "guillain-barre-syndrome", "charcot-marie-tooth-disease"],
        "neuromuscular-junction": ["myasthenia-gravis", "lambert-eaton-myasthenic-syndrome", "botulism"],
        "corticospinal-tract": ["upper-motor-neuron-lesion", "amyotrophic-lateral-sclerosis", "subacute-combined-degeneration"],
        "upper-motor-neuron-lesion": ["corticospinal-tract", "amyotrophic-lateral-sclerosis", "stroke"],
        "lower-motor-neuron-lesion": ["amyotrophic-lateral-sclerosis", "peripheral-nerves", "electromyography"],
        "neurologic-examination": ["cranial-nerves", "upper-motor-neuron-lesion", "lower-motor-neuron-lesion", "glasgow-coma-scale"],
        "electroencephalography": ["epilepsy", "encephalitis", "creutzfeldt-jakob-disease"],
        "nerve-conduction-study": ["electromyography", "polyneuropathy", "guillain-barre-syndrome", "chronic-inflammatory-demyelinating-polyneuropathy"],
        "electromyography": ["nerve-conduction-study", "amyotrophic-lateral-sclerosis", "myasthenia-gravis", "muscular-dystrophy"],
        "evoked-potential-test": ["multiple-sclerosis", "neuromyelitis-optica"],
        "brain-computed-tomography": ["stroke", "intracerebral-hemorrhage", "subarachnoid-hemorrhage"],
        "brain-magnetic-resonance-imaging": ["ischemic-stroke", "multiple-sclerosis", "brain-tumor"],
        "lumbar-puncture": ["cerebrospinal-fluid-analysis", "acute-bacterial-meningitis", "encephalitis", "subarachnoid-hemorrhage", "intracranial-hypotension"],
        "epilepsy": ["focal-seizure", "generalized-tonic-clonic-seizure", "absence-seizure", "status-epilepticus", "electroencephalography", "anti-seizure-medications"],
        "status-epilepticus": ["benzodiazepines", "phenytoin", "levetiracetam", "valproate"],
        "anti-seizure-medications": ["phenytoin", "valproate", "carbamazepine", "ethosuximide", "lamotrigine", "levetiracetam", "topiramate", "phenobarbital"],
        "phenytoin": ["anti-seizure-medications", "status-epilepticus"],
        "ethosuximide": ["absence-seizure", "anti-seizure-medications"],
        "lamotrigine": ["anti-seizure-medications", "stevens-johnson-syndrome-toxic-epidermal-necrolysis"],
        "levetiracetam": ["anti-seizure-medications", "status-epilepticus"],
        "topiramate": ["anti-seizure-medications", "migraine"],
        "phenobarbital": ["anti-seizure-medications"],
        "headache": ["migraine", "tension-type-headache", "cluster-headache", "raised-intracranial-pressure", "subarachnoid-hemorrhage", "giant-cell-arteritis"],
        "migraine": ["triptans", "ergot-alkaloids", "topiramate"],
        "cluster-headache": ["triptans", "oxygen-therapy"],
        "raised-intracranial-pressure": ["brain-computed-tomography", "lumbar-puncture"],
        "intracranial-hypotension": ["lumbar-puncture", "headache"],
        "giant-cell-arteritis": ["systemic-corticosteroids"],
        "stroke": ["ischemic-stroke", "transient-ischemic-attack", "intracerebral-hemorrhage", "subarachnoid-hemorrhage", "brain-computed-tomography", "brain-magnetic-resonance-imaging"],
        "ischemic-stroke": ["transient-ischemic-attack", "lacunar-infarction", "toast-stroke-classification", "alteplase", "stroke-thrombolysis", "mechanical-thrombectomy", "antiplatelet-therapy", "statins"],
        "transient-ischemic-attack": ["ischemic-stroke", "antiplatelet-therapy", "statins"],
        "lacunar-infarction": ["ischemic-stroke", "hypertension", "diabetes-mellitus"],
        "intracerebral-hemorrhage": ["stroke", "hypertension", "brain-computed-tomography"],
        "subarachnoid-hemorrhage": ["cerebral-aneurysm", "nimodipine", "aneurysm-clipping-coiling", "lumbar-puncture"],
        "cerebral-aneurysm": ["subarachnoid-hemorrhage", "aneurysm-clipping-coiling"],
        "cerebral-arteriovenous-malformation": ["intracerebral-hemorrhage", "epilepsy"],
        "alteplase": ["stroke-thrombolysis", "ischemic-stroke"],
        "nimodipine": ["subarachnoid-hemorrhage"],
        "stroke-thrombolysis": ["alteplase", "ischemic-stroke"],
        "mechanical-thrombectomy": ["ischemic-stroke"],
        "frontotemporal-dementia": ["dementia"],
        "dementia-with-lewy-bodies": ["dementia", "parkinson-disease"],
        "parkinson-disease": ["basal-ganglia", "levodopa", "dopamine-agonists", "mao-b-inhibitors", "dementia-with-lewy-bodies"],
        "essential-tremor": ["parkinson-disease", "beta-blockers"],
        "huntington-disease": ["basal-ganglia", "dementia"],
        "central-pontine-myelinolysis": ["hyponatremia", "brainstem"],
        "subacute-combined-degeneration": ["vitamin-b12-deficiency", "spinal-cord", "corticospinal-tract"],
        "levodopa": ["parkinson-disease"],
        "dopamine-agonists": ["parkinson-disease"],
        "mao-b-inhibitors": ["parkinson-disease"],
        "amyotrophic-lateral-sclerosis": ["upper-motor-neuron-lesion", "lower-motor-neuron-lesion", "electromyography"],
        "multiple-sclerosis": ["evoked-potential-test", "brain-magnetic-resonance-imaging", "spinal-cord", "systemic-corticosteroids"],
        "neuromyelitis-optica": ["multiple-sclerosis", "plasma-exchange", "spinal-cord"],
        "progressive-multifocal-leukoencephalopathy": ["hiv-infection", "opportunistic-infection"],
        "acute-disseminated-encephalomyelitis": ["multiple-sclerosis", "systemic-corticosteroids"],
        "chronic-inflammatory-demyelinating-polyneuropathy": ["guillain-barre-syndrome", "intravenous-immunoglobulin", "plasma-exchange"],
        "guillain-barre-syndrome": ["campylobacter-infection", "intravenous-immunoglobulin", "plasma-exchange", "nerve-conduction-study"],
        "diabetic-neuropathy": ["diabetes-mellitus", "peripheral-nerves", "polyneuropathy"],
        "polyneuropathy": ["peripheral-nerves", "nerve-conduction-study", "diabetic-neuropathy"],
        "cranial-nerve-palsy": ["cranial-nerves", "diabetic-neuropathy"],
        "myasthenia-gravis": ["neuromuscular-junction", "electromyography", "intravenous-immunoglobulin", "plasma-exchange"],
        "lambert-eaton-myasthenic-syndrome": ["neuromuscular-junction", "paraneoplastic-syndrome", "small-cell-lung-cancer"],
        "botulism": ["neuromuscular-junction"],
        "muscular-dystrophy": ["duchenne-muscular-dystrophy", "becker-muscular-dystrophy", "electromyography"],
        "polymyositis-dermatomyositis": ["electromyography", "systemic-corticosteroids"],
        "hypokalemic-periodic-paralysis": ["hypokalemia", "hyperthyroidism"],
        "acute-intermittent-porphyria": ["hyponatremia", "abdominal-pain"],
        "intravenous-immunoglobulin": ["guillain-barre-syndrome", "chronic-inflammatory-demyelinating-polyneuropathy", "myasthenia-gravis"],
        "plasma-exchange": ["guillain-barre-syndrome", "neuromyelitis-optica", "myasthenia-gravis"],
        "surgical-nutrition": ["enteral-nutrition", "parenteral-nutrition", "refeeding-syndrome", "malnutrition", "wound-dehiscence"],
        "enteral-nutrition": ["surgical-nutrition"],
        "parenteral-nutrition": ["surgical-nutrition", "catheter-related-bloodstream-infection"],
        "refeeding-syndrome": ["malnutrition", "hypophosphatemia"],
        "shock": ["hypovolemic-shock", "hemorrhagic-shock", "septic-shock", "neurogenic-shock", "fluid-resuscitation"],
        "hypovolemic-shock": ["shock", "fluid-resuscitation"],
        "hemorrhagic-shock": ["shock", "massive-transfusion-protocol", "damage-control-surgery", "lethal-triad-trauma"],
        "septic-shock": ["shock", "surgical-site-infection", "fluid-resuscitation"],
        "neurogenic-shock": ["spinal-cord-injury", "shock"],
        "surgical-site-infection": ["septic-shock", "necrotizing-fasciitis", "wound-dehiscence"],
        "wound-dehiscence": ["surgical-site-infection", "malnutrition"],
        "anastomotic-leak": ["septic-shock", "intra-abdominal-abscess"],
        "postoperative-ileus": ["hypokalemia", "abdominal-pain"],
        "fluid-resuscitation": ["shock", "lactated-ringer-solution", "normal-saline"],
        "massive-transfusion-protocol": ["hemorrhagic-shock", "blood-transfusion", "coagulation-tests"],
        "damage-control-surgery": ["hemorrhagic-shock", "lethal-triad-trauma", "abdominal-trauma"],
        "lethal-triad-trauma": ["damage-control-surgery", "hemorrhagic-shock"],
        "focused-assessment-with-sonography-for-trauma": ["abdominal-trauma", "hemorrhagic-shock"],
        "abdominal-trauma": ["focused-assessment-with-sonography-for-trauma", "damage-control-surgery", "hemorrhagic-shock"],
        "organ-transplantation": ["transplant-rejection", "hla-crossmatch", "organ-preservation", "liver-transplantation", "kidney-transplantation", "lung-transplantation", "immunosuppressants"],
        "transplant-rejection": ["organ-transplantation", "immunosuppressants", "kidney-transplant-rejection"],
        "hla-crossmatch": ["organ-transplantation", "transplant-rejection"],
        "liver-transplantation": ["organ-transplantation", "liver-cirrhosis", "hepatocellular-carcinoma"],
        "kidney-transplantation": ["organ-transplantation", "kidney-transplant-rejection"],
        "lung-transplantation": ["organ-transplantation", "pulmonary-hypertension"],
        "laparoscopy": ["abdominal-trauma"],
        "thoracoscopy": ["pleura", "lung-cancer"],
        "medical-ethics": ["informed-consent", "brain-death"],
        "coma": ["glasgow-coma-scale", "brain-death", "head-trauma", "raised-intracranial-pressure"],
        "brain-death": ["coma", "medical-ethics", "organ-transplantation"],
        "head-trauma": ["traumatic-brain-injury", "epidural-hematoma", "subdural-hematoma", "diffuse-axonal-injury", "cerebral-contusion", "skull-fracture", "brain-computed-tomography"],
        "traumatic-brain-injury": ["head-trauma", "raised-intracranial-pressure", "glasgow-coma-scale", "decompressive-craniectomy"],
        "epidural-hematoma": ["head-trauma", "skull-fracture", "brain-computed-tomography"],
        "subdural-hematoma": ["head-trauma", "brain-computed-tomography"],
        "diffuse-axonal-injury": ["traumatic-brain-injury", "brain-magnetic-resonance-imaging"],
        "cerebral-contusion": ["traumatic-brain-injury", "brain-computed-tomography"],
        "skull-fracture": ["head-trauma", "epidural-hematoma"],
        "raised-intracranial-pressure": ["monro-kellie-doctrine", "intracranial-pressure-monitoring", "mannitol", "hypertonic-saline", "decompressive-craniectomy"],
        "monro-kellie-doctrine": ["raised-intracranial-pressure"],
        "intracranial-pressure-monitoring": ["raised-intracranial-pressure", "traumatic-brain-injury"],
        "mannitol": ["raised-intracranial-pressure"],
        "hypertonic-saline": ["raised-intracranial-pressure", "hyponatremia"],
        "decompressive-craniectomy": ["raised-intracranial-pressure", "traumatic-brain-injury", "ischemic-stroke"],
        "subarachnoid-hemorrhage": ["cerebral-aneurysm", "cerebral-vasospasm", "hydrocephalus", "nimodipine", "aneurysm-clipping-coiling"],
        "cerebral-aneurysm": ["subarachnoid-hemorrhage", "aneurysm-clipping-coiling"],
        "cerebral-vasospasm": ["subarachnoid-hemorrhage", "nimodipine"],
        "cerebral-arteriovenous-malformation": ["intracerebral-hemorrhage", "cavernous-malformation", "carotid-cavernous-fistula"],
        "cavernous-malformation": ["cerebral-arteriovenous-malformation", "epilepsy"],
        "carotid-cavernous-fistula": ["cranial-nerves", "cerebral-arteriovenous-malformation"],
        "hydrocephalus": ["normal-pressure-hydrocephalus", "ventriculoperitoneal-shunt", "external-ventricular-drain", "raised-intracranial-pressure"],
        "normal-pressure-hydrocephalus": ["hydrocephalus", "dementia"],
        "ventriculoperitoneal-shunt": ["hydrocephalus"],
        "external-ventricular-drain": ["hydrocephalus", "intracranial-pressure-monitoring"],
        "trigeminal-neuralgia": ["cranial-nerves", "carbamazepine", "microvascular-decompression", "multiple-sclerosis"],
        "microvascular-decompression": ["trigeminal-neuralgia"],
        "herniated-intervertebral-disc": ["spinal-stenosis", "spinal-cord", "neurologic-examination"],
        "spinal-stenosis": ["cervical-myelopathy", "herniated-intervertebral-disc", "spondylolisthesis"],
        "cervical-myelopathy": ["spinal-stenosis", "upper-motor-neuron-lesion", "spinal-cord"],
        "spinal-cord-injury": ["neurogenic-shock", "spinal-cord", "cervical-spine-fracture"],
        "cervical-spine-fracture": ["spinal-cord-injury"],
        "spondylolisthesis": ["spinal-stenosis"],
        "scoliosis": ["spinal-cord"],
        "spinal-tumor": ["spinal-cord-compression", "brain-tumor"],
        "spina-bifida": ["hydrocephalus"],
        "brain-tumor": ["glioma", "glioblastoma", "meningioma", "vestibular-schwannoma", "pituitary-adenoma", "pediatric-brain-tumor", "raised-intracranial-pressure"],
        "glioma": ["astrocytoma", "oligodendroglioma", "glioblastoma", "brain-tumor"],
        "glioblastoma": ["glioma", "radiation-therapy", "chemotherapy"],
        "astrocytoma": ["glioma"],
        "oligodendroglioma": ["glioma"],
        "ependymoma": ["brain-tumor", "spinal-tumor"],
        "choroid-plexus-tumor": ["hydrocephalus", "brain-tumor"],
        "medulloblastoma": ["pediatric-brain-tumor", "brain-tumor"],
        "vestibular-schwannoma": ["cranial-nerves", "neurofibromatosis-type-1"],
        "meningioma": ["brain-tumor"],
        "hemangioblastoma": ["von-hippel-lindau-disease", "brain-tumor"],
        "craniopharyngioma": ["pituitary-gland", "pituitary-adenoma"],
        "intracranial-germ-cell-tumor": ["brain-tumor"],
        "epidermoid-cyst": ["brain-tumor", "trigeminal-neuralgia"],
        "idiopathic-intracranial-hypertension": ["raised-intracranial-pressure", "papilledema"],
        "peripheral-arterial-disease": ["atherosclerosis", "ankle-brachial-index", "acute-limb-ischemia", "critical-limb-ischemia", "revascularization", "statins", "antiplatelet-therapy"],
        "acute-limb-ischemia": ["peripheral-arterial-disease", "anticoagulation", "revascularization"],
        "critical-limb-ischemia": ["peripheral-arterial-disease", "ankle-brachial-index", "revascularization"],
        "ankle-brachial-index": ["peripheral-arterial-disease"],
        "endovascular-aneurysm-repair": ["aortic-aneurysm", "revascularization"],
        "aortic-dissection-surgery": ["aortic-dissection", "beta-blockers"],
        "valve-replacement-repair": ["heart-valves", "aortic-stenosis", "aortic-regurgitation", "mitral-stenosis", "mitral-regurgitation", "warfarin"],
        "heart-transplantation": ["heart-failure", "organ-transplantation", "transplant-rejection", "immunosuppressants"],
        "colonic-volvulus": ["colon", "colonoscopy"],
        "colonic-pseudo-obstruction": ["postoperative-ileus", "colon", "electrolyte-disorders"],
        "diverticular-disease": ["diverticulitis", "lower-gastrointestinal-bleeding", "colonoscopy"],
        "diverticulitis": ["diverticular-disease", "intra-abdominal-abscess", "colectomy"],
        "colonic-angiodysplasia": ["lower-gastrointestinal-bleeding", "colonoscopy"],
        "colorectal-polyp": ["colorectal-cancer", "colonoscopy", "familial-adenomatous-polyposis"],
        "familial-adenomatous-polyposis": ["colorectal-polyp", "colorectal-cancer", "colectomy"],
        "lynch-syndrome": ["colorectal-cancer", "genetic-counseling"],
        "appendicitis": ["appendectomy", "abdominal-pain", "intra-abdominal-abscess"],
        "appendectomy": ["appendicitis", "laparoscopy"],
        "hemorrhoids": ["anal-canal", "lower-gastrointestinal-bleeding"],
        "anal-fissure": ["anal-canal", "crohn-disease"],
        "anorectal-abscess-fistula": ["anal-canal", "crohn-disease", "surgical-site-infection"],
        "colectomy": ["colorectal-cancer", "inflammatory-bowel-disease", "diverticulitis", "ostomy"],
        "low-anterior-resection": ["colorectal-cancer", "anastomotic-leak", "ostomy"],
        "abdominoperineal-resection": ["colorectal-cancer", "ostomy"],
        "ostomy": ["colectomy", "low-anterior-resection", "abdominoperineal-resection"],
        "goiter": ["thyroid-gland", "hyperthyroidism", "hypothyroidism", "thyroid-nodule"],
        "thyroid-nodule": ["thyroid-ultrasonography", "fine-needle-aspiration-cytology", "thyroid-cancer", "thyroidectomy"],
        "hashimoto-thyroiditis": ["hypothyroidism", "autoimmune-thyroid-disease", "thyroid-function-tests"],
        "subacute-thyroiditis": ["hyperthyroidism", "hypothyroidism", "thyroid-function-tests"],
        "papillary-thyroid-carcinoma": ["thyroid-cancer", "thyroidectomy", "thyroid-ultrasonography"],
        "follicular-thyroid-carcinoma": ["thyroid-cancer", "thyroidectomy", "fine-needle-aspiration-cytology"],
        "medullary-thyroid-carcinoma": ["thyroid-cancer", "multiple-endocrine-neoplasia", "men2-syndrome"],
        "anaplastic-thyroid-carcinoma": ["thyroid-cancer", "airways"],
        "thyroidectomy": ["thyroid-nodule", "thyroid-cancer", "hypocalcemia", "recurrent-laryngeal-nerve-injury"],
        "thyroid-ultrasonography": ["thyroid-nodule", "fine-needle-aspiration-cytology"],
        "fine-needle-aspiration-cytology": ["thyroid-nodule", "thyroid-ultrasonography"],
        "parathyroid-carcinoma": ["hyperparathyroidism", "hypercalcemia", "parathyroidectomy"],
        "parathyroidectomy": ["hyperparathyroidism", "hypocalcemia", "parathyroid-carcinoma"],
        "insulinoma": ["hypoglycemia", "multiple-endocrine-neoplasia", "men1-syndrome"],
        "gastrinoma": ["peptic-ulcer-disease", "multiple-endocrine-neoplasia", "men1-syndrome"],
        "vipoma": ["diarrhea", "hypokalemia"],
        "glucagonoma": ["diabetes-mellitus", "necrolytic-migratory-erythema"],
        "multiple-endocrine-neoplasia": ["men1-syndrome", "men2-syndrome", "genetic-counseling"],
        "men1-syndrome": ["multiple-endocrine-neoplasia", "hyperparathyroidism", "pituitary-adenoma", "insulinoma", "gastrinoma"],
        "men2-syndrome": ["multiple-endocrine-neoplasia", "medullary-thyroid-carcinoma", "pheochromocytoma", "primary-aldosteronism"],
        "adrenal-incidentaloma": ["adrenal-gland", "pheochromocytoma", "primary-aldosteronism", "cushing-syndrome"],
        "adrenalectomy": ["adrenal-incidentaloma", "pheochromocytoma", "primary-aldosteronism", "cushing-syndrome"],
        "pressure-injury": ["skin-graft", "surgical-flap", "surgical-nutrition"],
        "skin-graft": ["skin", "wound-dehiscence", "pressure-injury"],
        "surgical-flap": ["skin-graft", "pressure-injury"],
        "cleft-lip-palate-repair": ["cleft-lip-palate"],
        "syndactyly": ["skin-graft", "surgical-flap"],
        "polydactyly": ["syndactyly"],
        "blepharoplasty": ["cranial-nerves"],
        "breast-augmentation": ["breast-cancer"],
        "anal-canal": ["colon", "hemorrhoids", "anal-fissure", "anorectal-abscess-fistula"],
        "colorectal-physiology": ["colon", "anal-canal", "diarrhea", "constipation"],
        "gastric-outlet-obstruction": ["peptic-ulcer-disease", "gastric-cancer", "metabolic-alkalosis"],
        "perforated-peptic-ulcer": ["peptic-ulcer-disease", "pneumoperitoneum", "septic-shock"],
        "gastrectomy": ["gastric-cancer", "dumping-syndrome", "billroth-reconstruction", "roux-en-y-reconstruction"],
        "vagotomy": ["peptic-ulcer-disease", "gastrectomy"],
        "billroth-reconstruction": ["gastrectomy", "afferent-loop-syndrome", "alkaline-reflux-gastritis"],
        "roux-en-y-reconstruction": ["gastrectomy", "alkaline-reflux-gastritis"],
        "dumping-syndrome": ["gastrectomy", "hypoglycemia"],
        "afferent-loop-syndrome": ["billroth-reconstruction", "acute-pancreatitis"],
        "alkaline-reflux-gastritis": ["gastrectomy", "gastritis"],
        "small-bowel-obstruction": ["adhesive-small-bowel-obstruction", "strangulated-bowel-obstruction", "intussusception", "gallstone-ileus", "small-intestine"],
        "adhesive-small-bowel-obstruction": ["small-bowel-obstruction", "postoperative-ileus"],
        "strangulated-bowel-obstruction": ["small-bowel-obstruction", "septic-shock", "lactic-acidosis"],
        "small-bowel-tumor": ["small-bowel-adenocarcinoma", "gastrointestinal-carcinoid-tumor", "gastrointestinal-stromal-tumor", "small-intestine"],
        "small-bowel-adenocarcinoma": ["small-bowel-tumor", "crohn-disease", "familial-adenomatous-polyposis"],
        "gastrointestinal-carcinoid-tumor": ["carcinoid-syndrome", "small-bowel-tumor", "tumor-markers"],
        "carcinoid-syndrome": ["gastrointestinal-carcinoid-tumor", "diarrhea", "heart-valves"],
        "hepatic-hemangioma": ["liver", "liver-function-tests"],
        "focal-nodular-hyperplasia": ["liver", "hepatic-adenoma"],
        "hepatic-adenoma": ["liver", "hepatocellular-carcinoma"],
        "hepatectomy": ["hepatocellular-carcinoma", "hepatic-adenoma", "liver-transplantation"],
        "radiofrequency-ablation": ["hepatocellular-carcinoma", "hepatectomy"],
        "acute-acalculous-cholecystitis": ["acute-cholecystitis", "cholecystectomy", "percutaneous-cholecystostomy"],
        "gallstone-ileus": ["cholelithiasis", "small-bowel-obstruction"],
        "biliary-pancreatitis": ["acute-pancreatitis", "cholelithiasis", "choledocholithiasis", "ercp"],
        "cholangiocarcinoma": ["biliary-tract", "choledochal-cyst", "mrcp", "ercp"],
        "choledochal-cyst": ["cholangiocarcinoma", "acute-cholangitis", "mrcp"],
        "gallbladder-cancer": ["cholelithiasis", "cholecystectomy", "cholangiocarcinoma"],
        "mrcp": ["choledocholithiasis", "cholangiocarcinoma", "pancreatic-cancer", "biliary-pancreatitis"],
        "percutaneous-cholecystostomy": ["acute-cholecystitis", "acute-acalculous-cholecystitis"],
        "pancreatic-pseudocyst": ["acute-pancreatitis", "chronic-pancreatitis"],
        "pancreatic-necrosis": ["acute-pancreatitis", "septic-shock"],
        "periampullary-cancer": ["pancreatic-cancer", "cholangiocarcinoma", "pancreaticoduodenectomy"],
        "pancreatic-neuroendocrine-tumor": ["insulinoma", "gastrinoma", "vipoma", "glucagonoma", "multiple-endocrine-neoplasia"],
        "intraductal-papillary-mucinous-neoplasm": ["pancreatic-cancer", "mrcp"],
        "mucinous-cystic-neoplasm-pancreas": ["pancreatic-cancer", "pancreatic-pseudocyst"],
        "pancreaticoduodenectomy": ["pancreatic-cancer", "periampullary-cancer", "cholangiocarcinoma", "pancreatic-fistula"],
        "distal-pancreatectomy": ["pancreatic-cancer", "pancreatic-neuroendocrine-tumor", "pancreatic-fistula"],
        "pancreatic-fistula": ["pancreaticoduodenectomy", "distal-pancreatectomy", "intra-abdominal-abscess"],
        "fibroadenoma": ["breast-ultrasonography", "core-needle-biopsy-breast"],
        "fibrocystic-change": ["breast-ultrasonography", "breast-cancer"],
        "mastitis": ["breast-abscess", "staphylococcus-aureus-infection"],
        "breast-abscess": ["mastitis", "breast-ultrasonography"],
        "intraductal-papilloma": ["breast-cancer", "core-needle-biopsy-breast"],
        "phyllodes-tumor": ["fibroadenoma", "breast-conserving-surgery"],
        "ductal-carcinoma-in-situ": ["breast-cancer", "mammography", "breast-conserving-surgery", "mastectomy", "sentinel-lymph-node-biopsy"],
        "lobular-carcinoma-in-situ": ["breast-cancer", "mammography", "endocrine-therapy-for-breast-cancer"],
        "invasive-ductal-carcinoma": ["breast-cancer", "sentinel-lymph-node-biopsy", "mastectomy"],
        "invasive-lobular-carcinoma": ["breast-cancer", "sentinel-lymph-node-biopsy"],
        "paget-disease-of-breast": ["breast-cancer", "ductal-carcinoma-in-situ", "core-needle-biopsy-breast"],
        "breast-ultrasonography": ["breast-cancer", "fibroadenoma", "breast-abscess", "core-needle-biopsy-breast"],
        "core-needle-biopsy-breast": ["breast-ultrasonography", "breast-cancer"],
        "sentinel-lymph-node-biopsy": ["breast-cancer", "ductal-carcinoma-in-situ", "axillary-lymph-node-dissection"],
        "breast-conserving-surgery": ["breast-cancer", "ductal-carcinoma-in-situ", "radiation-therapy"],
        "axillary-lymph-node-dissection": ["breast-cancer", "sentinel-lymph-node-biopsy"],
        "pectus-excavatum": ["nuss-procedure", "ravitch-procedure", "chest-wall-tumor"],
        "pectus-carinatum": ["ravitch-procedure", "chest-wall-tumor"],
        "poland-syndrome": ["chest-wall-tumor"],
        "thoracic-outlet-syndrome": ["peripheral-nerves", "revascularization"],
        "chest-wall-tumor": ["pectus-excavatum", "pectus-carinatum", "surgical-flap"],
        "nuss-procedure": ["pectus-excavatum"],
        "ravitch-procedure": ["pectus-excavatum", "pectus-carinatum"],
        "malignant-pleural-effusion": ["pleural-effusion", "thoracentesis", "pleurodesis", "lung-cancer"],
        "chylothorax": ["pleural-effusion", "thoracentesis", "chest-tube-thoracostomy"],
        "mesothelioma": ["pleura", "malignant-pleural-effusion", "pleurodesis"],
        "pleurodesis": ["pneumothorax", "malignant-pleural-effusion", "chylothorax"],
        "decortication": ["empyema", "pleura", "thoracoscopy"],
        "mediastinal-mass": ["thymoma", "mediastinal-germ-cell-tumor", "lymphoma", "bronchoscopy"],
        "thymoma": ["mediastinal-mass", "myasthenia-gravis"],
        "mediastinal-germ-cell-tumor": ["mediastinal-mass", "tumor-markers"],
        "tracheostomy": ["airways", "mechanical-ventilation", "tracheal-tumor"],
        "tracheal-tumor": ["airways", "bronchoscopy", "tracheostomy"],
        "thoracic-trauma": ["flail-chest", "open-pneumothorax", "hemothorax", "tracheobronchial-injury", "blunt-aortic-injury", "neck-trauma", "chest-tube-thoracostomy"],
        "flail-chest": ["thoracic-trauma", "mechanical-ventilation", "acute-respiratory-distress-syndrome"],
        "open-pneumothorax": ["thoracic-trauma", "pneumothorax", "chest-tube-thoracostomy"],
        "hemothorax": ["thoracic-trauma", "chest-tube-thoracostomy", "hemorrhagic-shock"],
        "tracheobronchial-injury": ["thoracic-trauma", "airways", "bronchoscopy"],
        "blunt-aortic-injury": ["thoracic-trauma", "aortic-aneurysm", "endovascular-aneurysm-repair"],
        "neck-trauma": ["thoracic-trauma", "airways", "esophageal-perforation"],
        "zenker-diverticulum": ["dysphagia", "esophagus"],
        "caustic-esophageal-injury": ["esophageal-perforation", "upper-endoscopy", "esophageal-cancer"],
        "esophageal-perforation": ["esophagus", "septic-shock", "empyema"],
        "esophageal-foreign-body": ["upper-endoscopy", "esophageal-perforation"],
        "esophagectomy": ["esophageal-cancer", "esophageal-perforation", "anastomotic-leak"],
        "branchial-cleft-remnant": ["thyroglossal-duct-cyst", "lymphangioma-cystic-hygroma"],
        "thyroglossal-duct-cyst": ["branchial-cleft-remnant", "thyroid-gland"],
        "lymphangioma-cystic-hygroma": ["branchial-cleft-remnant", "airways"],
        "congenital-muscular-torticollis": ["developmental-milestones"],
        "cystic-fibrosis": ["meconium-ileus", "bronchiectasis", "pancreas"],
        "meconium-ileus": ["cystic-fibrosis", "small-bowel-obstruction"],
        "intestinal-atresia": ["duodenal-atresia", "jejunoileal-atresia", "small-bowel-obstruction"],
        "jejunoileal-atresia": ["intestinal-atresia", "small-intestine"],
        "intestinal-malrotation": ["ladd-procedure", "small-bowel-obstruction"],
        "necrotizing-enterocolitis": ["septic-shock", "pneumoperitoneum", "short-bowel-syndrome"],
        "imperforate-anus": ["anal-canal", "vesicoureteral-reflux"],
        "pyloromyotomy": ["hypertrophic-pyloric-stenosis", "metabolic-alkalosis"],
        "ladd-procedure": ["intestinal-malrotation", "appendectomy"],
        "kasai-portoenterostomy": ["biliary-atresia", "liver-transplantation"],
        "prune-belly-syndrome": ["cryptorchidism", "hydronephrosis"],
        "inguinal-hernia": ["hydrocele", "small-bowel-obstruction"],
        "hydrocele": ["inguinal-hernia", "cryptorchidism"],
        "cryptorchidism": ["orchiopexy", "testicular-torsion"],
        "retractile-testis": ["cryptorchidism"],
        "testicular-torsion": ["orchiopexy", "cryptorchidism"],
        "hypospadias": ["hypospadias-repair", "cryptorchidism"],
        "orchiopexy": ["cryptorchidism", "testicular-torsion"],
        "hypospadias-repair": ["hypospadias"],
        "rhabdomyosarcoma": ["tumor-staging", "chemotherapy", "radiation-therapy"],
        "craniosynostosis": ["raised-intracranial-pressure", "cranial-nerves"],
        "congenital-pulmonary-airway-malformation": ["congenital-diaphragmatic-hernia", "neonatal-respiratory-distress-syndrome", "lung"],
        "renal-cyst": ["bosniak-renal-cyst-classification", "kidney", "renal-cell-carcinoma"],
        "bosniak-renal-cyst-classification": ["renal-cyst", "renal-cell-carcinoma"],
        "renal-trauma": ["kidney", "abdominal-trauma", "hemorrhagic-shock"],
        "renal-abscess": ["pyelonephritis", "urinary-tract-infection", "percutaneous-nephrostomy"],
        "emphysematous-pyelonephritis": ["pyelonephritis", "diabetes-mellitus", "percutaneous-nephrostomy"],
        "renal-cell-carcinoma": ["kidney", "partial-nephrectomy", "radical-nephrectomy", "renal-angiomyolipoma", "renal-oncocytoma"],
        "renal-oncocytoma": ["renal-cell-carcinoma", "kidney"],
        "renal-angiomyolipoma": ["renal-cell-carcinoma", "tuberous-sclerosis-complex", "kidney"],
        "upper-tract-urothelial-carcinoma": ["bladder-cancer", "nephroureterectomy", "ureteroscopy", "cystoscopy"],
        "partial-nephrectomy": ["renal-cell-carcinoma", "kidney"],
        "radical-nephrectomy": ["renal-cell-carcinoma", "wilms-tumor"],
        "nephroureterectomy": ["upper-tract-urothelial-carcinoma", "bladder-cancer"],
        "ureteral-duplication": ["vesicoureteral-reflux", "ectopic-ureter", "urinary-tract-infection"],
        "ureteropelvic-junction-obstruction": ["hydronephrosis", "nephrolithiasis", "urinary-tract-infection"],
        "ectopic-ureter": ["ureteral-duplication", "urinary-incontinence"],
        "interstitial-cystitis": ["cystoscopy", "urinary-incontinence", "overactive-bladder"],
        "ureteral-injury": ["ureteral-stent", "percutaneous-nephrostomy"],
        "bladder-trauma": ["cystoscopy", "urethral-injury"],
        "urethral-injury": ["urethral-stricture", "bladder-trauma"],
        "urethral-stricture": ["uroflowmetry", "cystoscopy", "urethral-injury"],
        "phimosis": ["penile-cancer", "paraphimosis"],
        "paraphimosis": ["phimosis"],
        "bladder-cancer": ["bladder-carcinoma-in-situ", "cystoscopy", "transurethral-resection-bladder-tumor", "radical-cystectomy", "intravesical-bcg", "upper-tract-urothelial-carcinoma"],
        "bladder-carcinoma-in-situ": ["bladder-cancer", "intravesical-bcg", "radical-cystectomy"],
        "cystoscopy": ["bladder-cancer", "interstitial-cystitis", "urethral-stricture"],
        "transurethral-resection-bladder-tumor": ["bladder-cancer", "intravesical-bcg"],
        "radical-cystectomy": ["bladder-cancer", "ostomy"],
        "intravesical-bcg": ["bladder-cancer", "bladder-carcinoma-in-situ"],
        "prostatitis": ["urinary-tract-infection", "prostate-abscess", "prostate-specific-antigen"],
        "prostate-abscess": ["prostatitis", "cystoscopy"],
        "benign-prostatic-hyperplasia": ["prostate-zones", "prostate-specific-antigen", "alpha-1-blockers-urology", "five-alpha-reductase-inhibitors", "transurethral-resection-prostate", "urinary-incontinence"],
        "prostate-cancer": ["prostate-specific-antigen", "gleason-score", "prostate-biopsy", "radical-prostatectomy", "androgen-deprivation-therapy", "castration-resistant-prostate-cancer"],
        "castration-resistant-prostate-cancer": ["prostate-cancer", "androgen-deprivation-therapy", "chemotherapy"],
        "prostate-specific-antigen": ["prostate-cancer", "benign-prostatic-hyperplasia", "prostatitis", "five-alpha-reductase-inhibitors"],
        "gleason-score": ["prostate-cancer", "prostate-biopsy"],
        "prostate-biopsy": ["prostate-cancer", "gleason-score", "prostate-specific-antigen"],
        "transurethral-resection-prostate": ["benign-prostatic-hyperplasia", "hyponatremia"],
        "radical-prostatectomy": ["prostate-cancer", "erectile-dysfunction", "urinary-incontinence"],
        "androgen-deprivation-therapy": ["prostate-cancer", "lhrh-gnrh-agonists", "androgen-receptor-antagonists", "osteoporosis"],
        "alpha-1-blockers-urology": ["benign-prostatic-hyperplasia", "orthostatic-hypotension", "retrograde-ejaculation"],
        "five-alpha-reductase-inhibitors": ["benign-prostatic-hyperplasia", "prostate-specific-antigen"],
        "lhrh-gnrh-agonists": ["androgen-deprivation-therapy", "prostate-cancer"],
        "androgen-receptor-antagonists": ["androgen-deprivation-therapy", "prostate-cancer"],
        "staghorn-calculus": ["struvite-stone", "nephrolithiasis", "percutaneous-nephrolithotomy"],
        "struvite-stone": ["staghorn-calculus", "urinary-tract-infection", "nephrolithiasis"],
        "uric-acid-stone": ["nephrolithiasis", "gout"],
        "cystine-stone": ["nephrolithiasis"],
        "extracorporeal-shock-wave-lithotripsy": ["nephrolithiasis", "ureteral-stent"],
        "percutaneous-nephrolithotomy": ["nephrolithiasis", "staghorn-calculus", "percutaneous-nephrostomy"],
        "ureteroscopic-lithotripsy": ["nephrolithiasis", "ureteroscopy", "ureteral-stent"],
        "percutaneous-nephrostomy": ["nephrolithiasis", "renal-abscess", "ureteral-injury"],
        "ureteral-stent": ["nephrolithiasis", "ureteral-injury", "ureteroscopic-lithotripsy"],
        "urodynamic-study": ["uroflowmetry", "cystometry", "urethral-pressure-profile", "urinary-incontinence", "neurogenic-bladder"],
        "uroflowmetry": ["urodynamic-study", "benign-prostatic-hyperplasia", "urethral-stricture"],
        "cystometry": ["urodynamic-study", "neurogenic-bladder", "overactive-bladder"],
        "urethral-pressure-profile": ["urodynamic-study", "stress-urinary-incontinence"],
        "urinary-incontinence": ["stress-urinary-incontinence", "urge-incontinence", "overflow-incontinence", "neurogenic-bladder", "urodynamic-study"],
        "stress-urinary-incontinence": ["urinary-incontinence", "urethral-pressure-profile"],
        "urge-incontinence": ["urinary-incontinence", "overactive-bladder", "antimuscarinic-bladder-drugs"],
        "overflow-incontinence": ["urinary-incontinence", "benign-prostatic-hyperplasia", "neurogenic-bladder"],
        "neurogenic-bladder": ["urinary-incontinence", "detrusor-sphincter-dyssynergia", "urodynamic-study", "spinal-cord-injury"],
        "detrusor-sphincter-dyssynergia": ["neurogenic-bladder", "autonomic-dysreflexia"],
        "overactive-bladder": ["urge-incontinence", "antimuscarinic-bladder-drugs", "neurogenic-bladder"],
        "autonomic-dysreflexia": ["spinal-cord-injury", "neurogenic-bladder"],
        "nocturnal-enuresis": ["urinary-incontinence", "pediatric-dehydration"],
        "antimuscarinic-bladder-drugs": ["overactive-bladder", "urge-incontinence", "neurogenic-bladder"],
        "erectile-dysfunction": ["pde5-inhibitors", "male-infertility", "radical-prostatectomy", "penile-prosthesis"],
        "premature-ejaculation": ["erectile-dysfunction"],
        "retrograde-ejaculation": ["alpha-1-blockers-urology", "male-infertility", "transurethral-resection-prostate"],
        "male-infertility": ["semen-analysis", "varicocele", "erectile-dysfunction", "cryptorchidism", "male-reproductive-endocrine-axis"],
        "varicocele": ["male-infertility", "varicocelectomy"],
        "semen-analysis": ["male-infertility", "male-reproductive-endocrine-axis"],
        "nocturnal-penile-tumescence-test": ["erectile-dysfunction"],
        "pde5-inhibitors": ["erectile-dysfunction", "nitrates"],
        "penile-prosthesis": ["erectile-dysfunction"],
        "varicocelectomy": ["varicocele", "male-infertility"],
        "vasovasostomy": ["male-infertility"],
        "testicular-sperm-extraction": ["male-infertility", "semen-analysis"],
        "male-reproductive-endocrine-axis": ["male-infertility", "prostate-cancer", "androgen-deprivation-therapy"],
        "prostate-zones": ["prostate-cancer", "benign-prostatic-hyperplasia", "prostate-biopsy"],
        "lower-urinary-tract-function": ["urodynamic-study", "urinary-incontinence", "neurogenic-bladder"],
        "adrenal-androgen-excess": ["congenital-adrenal-hyperplasia", "adrenal-gland", "cushing-syndrome"],
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
        seed_page_path(seed).write_text(topic_page(seed, source_mentions, available_slugs, book_name, book_key), encoding="utf-8")

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
