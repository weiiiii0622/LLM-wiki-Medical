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


def topic_page(seed: TopicSeed, source_mentions: list[tuple[str, Path, list[str]]], available_slugs: set[str]) -> str:
    path = seed_page_path(seed)
    source_mentions = sorted(source_mentions, key=lambda item: source_relevance(seed, item))
    source_links = [wiki_link(source_path) for _, source_path, _ in source_mentions]
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
    detail = "\n".join(bullets) or "- 尚未擷取到足夠片段。"
    related = related_links(seed, available_slugs)
    related_block = "\n".join(f"- {link}" for link in related) if related else "- 待補。"
    return f"""---
type: {seed.kind}
status: draft
created: {TODAY}
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

{seed.summary} 本頁以 `醫(三)第1冊心胸內` 的章節內容自動整合，供後續查詢與人工精修。

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
    }
    slug_to_seed = {item.slug: item for item in SEEDS}
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

- [[sources/index]] - Source summaries catalog for `{book_name}`.

## Topic Categories

{cat_lines}

## Questions

- [[questions/index]] - Durable answers filed from useful queries.

## Maintenance Notes

- First textbook ingested topic-first on {TODAY}: `{book_name}`.
- Topic nodes are organized by medical entity or concept, not chapter title. Source chapter pages remain only as citation anchors.
"""


def overview(book_name: str, source_count: int, topic_count: int) -> str:
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

- 已 ingest textbook: `{book_name}`
- Chapter source summaries: {source_count}
- Topic-first nodes: {topic_count}

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
- Topic nodes created/updated: {len(matched_seeds)}
- Wiki files checked for links: {files_checked}
- Missing wiki links: {len(missing)}

## Topic Counts

{counts}

## Link Check

{missing_block}

## Notes

- This pass used deterministic keyword extraction plus curated first-book topic seeds.
- Topic pages are disease/treatment/guideline/drug/diagnostic/procedure/physiology/anatomy/concept nodes, not chapter-title buckets.
- Content is Mandarin-first with English medical terms included in titles and aliases where available.
- Guideline-sensitive and dosing-sensitive claims remain textbook-derived and need current official verification before clinical use.

## Recommended Next Lint

- Merge duplicate Chinese/English aliases if Obsidian graph shows separate nodes.
- Promote high-yield pages such as `Heart failure`, `ACS`, `Asthma`, `COPD`, `Pulmonary embolism`, and `Lung cancer` from auto-extracted notes into manually synthesized review pages.
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

    for seed in SEEDS:
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
    available_slugs = {seed.slug for seed in matched_seeds}
    for seed, source_mentions in mentions_by_seed.items():
        seed_page_path(seed).write_text(topic_page(seed, source_mentions, available_slugs), encoding="utf-8")

    category_counts: dict[str, int] = {}
    for kind in TYPE_DIR:
        seeds = [seed for seed in matched_seeds if seed.kind == kind]
        category_counts[kind] = len(seeds)
        (WIKI / TYPE_DIR[kind] / "index.md").write_text(category_index(kind, seeds), encoding="utf-8")

    source_page_list = [source_page_path(source_slug(book_key, idx)) for idx, *_ in chapter_texts]
    (WIKI / "sources" / "index.md").write_text(sources_index(source_page_list), encoding="utf-8")
    (WIKI / "index.md").write_text(main_index(category_counts, book_name), encoding="utf-8")
    (WIKI / "overview.md").write_text(overview(book_name, len(chapters), len(matched_seeds)), encoding="utf-8")
    report = health_report(book_name, len(chapters), matched_seeds, category_counts)
    (ROOT / "docs" / f"health-check-{TODAY}-{book_key}.md").write_text(report, encoding="utf-8")
    append_log(book_name, len(chapters), len(matched_seeds))

    print(f"book={book_name}")
    print(f"chapters={len(chapters)}")
    print(f"topic_nodes={len(matched_seeds)}")
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
