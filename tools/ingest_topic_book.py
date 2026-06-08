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
    TopicSeed("condition", "impetigo", "Impetigo (膿痂疹)", ("膿痂疹", "Impetigo"), "表淺皮膚感染，可由 GAS 或 S. aureus 造成。"),
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
    TopicSeed("condition", "giant-cell-arteritis", "Giant cell arteritis, GCA (巨細胞動脈炎)", ("Giant cell arteritis", "GCA", "temporal arteritis", "巨細胞動脈炎", "jaw claudication"), "老年人顳動脈與大血管炎，需注意視力喪失與 polymyalgia rheumatica 關聯。"),
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
    TopicSeed("procedure", "plasma-exchange", "Plasma exchange (血漿置換)", ("Plasma exchange", "plasmapheresis", "血漿置換"), "以血漿移除致病抗體或補充缺乏因子，TTP 等疾病可用。"),
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


ALL_SEEDS: tuple[TopicSeed, ...] = SEEDS + SECOND_BOOK_SEEDS + THIRD_BOOK_SEEDS + FOURTH_BOOK_SEEDS + FIFTH_BOOK_SEEDS


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
    part_order = {"第一篇": 1, "第二篇": 2, "第三篇": 3, "第四篇": 4}
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
