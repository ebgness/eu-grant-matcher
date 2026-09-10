from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, render_template, request

from src.ai_advisor import advise
from src.auto_refresh import DailyRefresh
from src.database import init_db, save_analysis
from src.document_profile import extract_text, profile_from_document
from src.export_reports import build_docx, build_xlsx
from src.historical_projects import load_projects, similar_projects
from src.pdf_report import build_pdf
from src.recommendations import build_recommendations
from src.real_scorer import load_calls, missing_profile_fields, parse_date, score_call, trl_range

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
BASE_DIR = Path(__file__).parent
CALLS_PATH = BASE_DIR / "data" / "processed" / "calls.json"
HISTORICAL_PATH = BASE_DIR / "data" / "historical_projects.json"
init_db()
DailyRefresh(BASE_DIR).start()

TRANSLATIONS = {
    "tr": {
        "kicker": "EU GRANT MATCH / CANLI FTOP VERİSİ",
        "title": "Projen için doğru çağrıyı bul.",
        "intro": "Proje bilgilerini gir veya profil dosyanı yükle. Sistem güncel AB çağrılarını karşılaştırır ve nedenlerini açıklar.",
        "profile": "Proje profili", "results": "Sonuçlar", "company": "Şirket adı",
        "country": "Ülke", "sector": "Sektör", "technologies": "Teknolojiler",
        "keywords": "Anahtar kelimeler", "summary": "Proje özeti", "trl": "TRL seviyesi",
        "budget": "Talep edilen bütçe (EUR)", "cofinancing": "Mevcut eş finansman (EUR)",
        "employees": "Çalışan sayısı",
        "gep": "GEP durumu", "no_gep": "Belirtilmedi / Yok", "has_gep": "Var",
        "score": "Çağrıları skorla", "upload": "Profil dosyanı sürükle bırak veya seç",
        "json_hint": "JSON formatı", "empty_title": "Henüz analiz yok",
        "empty_body": "Profilini doldurduğunda güncel FTOP çağrıları burada görünecek.",
        "missing": "Eksik alanlar", "preliminary": "Sonuçlar ön değerlendirmedir.",
        "suggestions": "öneri · ilk 10 sonuç", "deadline": "Son tarih",
        "unknown": "belirsiz", "rejected": "Elenen çağrılar", "risk": "RİSKLİ",
        "match": "UYGUN", "at_risk": "RİSKLİ", "rejected_reason": "Neden",
        "language": "Dil", "tr": "Türkçe", "en": "English",
        "official_portal": "Resmi Funding & Tenders Portal",
        "open_call": "Resmi çağrı sayfasını aç",
        "pdf_report": "PDF raporu oluştur", "json_report": "JSON raporu indir", "text_report": "TXT raporu indir",
        "excel_report": "Excel raporu indir", "word_report": "Word raporu indir",
        "recommendations": "Öneriler", "recommendation_intro": "Eksik bilgileri ve geçmiş kalıpları dikkate alan ilk tavsiyeler.",
        "ai_advisor": "AI danışman", "local_only": "Yerel ve açıklanabilir mod",
    },
    "en": {
        "kicker": "EU GRANT MATCH / LIVE FTOP DATA",
        "title": "Find the right call for your project.",
        "intro": "Enter your project details or upload a profile. The system compares live EU calls and explains the reasons.",
        "profile": "Project profile", "results": "Results", "company": "Company name",
        "country": "Country", "sector": "Sector", "technologies": "Technologies",
        "keywords": "Keywords", "summary": "Project summary", "trl": "TRL level",
        "budget": "Requested budget (EUR)", "cofinancing": "Available co-financing (EUR)",
        "employees": "Employee count",
        "gep": "GEP status", "no_gep": "Not stated / No", "has_gep": "Yes",
        "score": "Score calls", "upload": "Drop or choose your profile file",
        "json_hint": "JSON format", "empty_title": "No analysis yet",
        "empty_body": "Your live FTOP matches will appear here after you submit a profile.",
        "missing": "Missing fields", "preliminary": "Results are preliminary until these fields are complete.",
        "suggestions": "matches · top 10", "deadline": "Deadline",
        "unknown": "unknown", "rejected": "Rejected calls", "risk": "AT RISK",
        "match": "MATCH", "at_risk": "AT RISK", "rejected_reason": "Reason",
        "language": "Language", "tr": "Türkçe", "en": "English",
        "official_portal": "Official Funding & Tenders Portal",
        "open_call": "Open official call page",
        "pdf_report": "Create PDF report", "json_report": "Download JSON report", "text_report": "Download TXT report",
        "excel_report": "Download Excel report", "word_report": "Download Word report",
        "recommendations": "Recommendations", "recommendation_intro": "Initial guidance based on missing information and observed call patterns.",
        "ai_advisor": "AI advisor", "local_only": "Local transparent mode",
    },
}


def translate_detail(detail: str, language: str) -> str:
    if language == "tr":
        return detail
    replacements = {
        "Şirket adı": "Company name", "Ülke": "Country", "Sektör": "Sector",
        "Proje özeti": "Project summary", "TRL seviyesi": "TRL level",
        "Konu uyumu:": "Topic alignment:", "TRL bilgisi eksik:": "TRL information missing:",
        "TRL uyumu:": "TRL alignment:", "Eylem türü tanımlı:": "Action type identified:",
        "IA şirket fonlama oranı dikkate alındı:": "IA company funding rate considered:",
        "Eylem türü doğrulanamadı:": "Action type could not be verified:",
        "Ülke uygunluğu bu özetten doğrulanamadı:": "Country eligibility could not be verified from this summary:",
        "GEP bu çağrı özetinde doğrulanamadı:": "GEP could not be verified from this summary:",
    }
    for source, target in replacements.items():
        detail = detail.replace(source, target)
    return detail


def localize_result(result: dict, language: str) -> dict:
    for item in result["scored"]:
        item["status"] = TRANSLATIONS[language]["match"] if item["score"] >= 70 else TRANSLATIONS[language]["at_risk"]
        item["details"] = [translate_detail(detail, language) for detail in item["details"]]
    for item in result["rejected"]:
        item["reasons"] = [translate_detail(reason, language) for reason in item["reasons"]]
    return result


def profile_from_form(form) -> dict:
    technologies = [item.strip() for item in form.get("technologies", "").split(",") if item.strip()]
    keywords = [item.strip() for item in form.get("keywords", "").split(",") if item.strip()]
    try:
        trl_level = int(form.get("trl_level", ""))
    except ValueError:
        trl_level = None
    def amount(name: str):
        try:
            return float(form.get(name, ""))
        except ValueError:
            return None
    try:
        employees = int(form.get("employees", ""))
    except ValueError:
        employees = None
    return {
        "company_name": form.get("company_name", "").strip(),
        "country": form.get("country", "").strip(),
        "sector": form.get("sector", "").strip(),
        "technologies": technologies,
        "keywords": keywords,
        "project_summary": form.get("project_summary", "").strip(),
        "trl_level": trl_level,
        "requested_budget_eur": amount("requested_budget_eur"),
        "available_cofinancing_eur": amount("available_cofinancing_eur"),
        "employees": employees,
        "organisation_type": "for_profit",
        "has_gep": form.get("has_gep") == "yes",
    }


def evaluate_profile(profile: dict) -> dict:
    calls = load_calls(CALLS_PATH)
    scored = []
    rejected = []
    from datetime import datetime, timezone

    for call in calls:
        deadline = parse_date(call["deadline"])
        if deadline and deadline < datetime.now(timezone.utc):
            rejected.append({"call": call, "reasons": ["Son başvuru tarihi geçmiş."]})
            continue
        score, details = score_call(profile, call)
        company_trl = profile.get("trl_level")
        call_trl = trl_range(call["text"])
        if isinstance(company_trl, int) and call_trl and not call_trl[0] <= company_trl <= call_trl[1]:
            rejected.append({
                "call": call,
                "reasons": [f"TRL uyumsuz: şirket TRL {company_trl}, çağrı TRL {call_trl[0]}-{call_trl[1]}"],
            })
            continue
        employees = profile.get("employees")
        call_text_lower = call["text"].lower()
        has_size_limit_signal = any(signal in call_text_lower for signal in ("small and medium-sized", "small mid-cap", "sme", "smEs".lower()))
        if isinstance(employees, int) and employees > 499 and has_size_limit_signal:
            rejected.append({
                "call": call,
                "reasons": [f"Çalışan sayısı uygun değil: şirket {employees}, çağrı KOBİ/Small Mid-cap sinyali içeriyor."],
            })
            continue
        scored.append({
            "score": score,
            "status": "UYGUN" if score >= 70 else "RISKLI",
            "call": call,
            "details": details,
        })
    scored.sort(key=lambda item: item["score"], reverse=True)
    return {"scored": scored[:10], "rejected": rejected[:10]}


@app.route("/", methods=["GET", "POST"])
def index():
    profile = {}
    result = None
    missing = []
    error = None
    language = request.form.get("language", request.args.get("language", "tr"))
    if language not in TRANSLATIONS:
        language = "tr"
    if request.method == "POST":
        try:
            uploaded = request.files.get("profile_file")
            if uploaded and uploaded.filename:
                content = uploaded.read()
                if not content:
                    raise ValueError("Yüklenen dosya boş. Lütfen içerik bulunan bir dosya seçin.")
                if len(content) > app.config["MAX_CONTENT_LENGTH"]:
                    raise ValueError("Dosya boyutu 10 MB sınırını aşıyor.")
                allowed_extensions = {".json", ".pdf", ".docx", ".txt", ".md"}
                from pathlib import Path
                if Path(uploaded.filename).suffix.lower() not in allowed_extensions:
                    raise ValueError("Desteklenen dosya türleri: JSON, PDF, DOCX, TXT ve MD.")
                if uploaded.filename.lower().endswith(".json"):
                    profile = json.loads(content.decode("utf-8"))
                else:
                    profile = profile_from_document(extract_text(uploaded.filename, content))
            else:
                profile = profile_from_form(request.form)
            missing = missing_profile_fields(profile)
            result = evaluate_profile(profile)
            result["recommendations"] = build_recommendations(profile, result["scored"], result["rejected"], language)
            historical = similar_projects(profile, load_projects(HISTORICAL_PATH))
            if historical:
                result["historical_projects"] = historical
                result["recommendations"].append(
                    f"Benzer geçmiş proje bulundu: {historical[0]['project'].get('title', 'Başlıksız proje')} (eşleşen terimler: {', '.join(historical[0]['matched_terms'][:8])})."
                )
            else:
                result["historical_projects"] = []
            result["ai_advisor"] = advise(profile, result, language)
            profile["analysis_id"] = save_analysis(profile, result)
            result = localize_result(result, language)
        except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
            error = f"Profil okunamadı: {exc}"
    localized_missing = missing
    if language == "en":
        localized_missing = [translate_detail(item, language) for item in missing]
    return render_template("index.html", profile=profile, result=result, missing=localized_missing, error=error, language=language, t=TRANSLATIONS[language])


@app.errorhandler(413)
def file_too_large(_error):
    return render_template("index.html", profile={}, result=None, missing=[], error="Dosya boyutu 10 MB sınırını aşıyor.", language="tr", t=TRANSLATIONS["tr"]), 413


@app.post("/report/pdf")
def pdf_report():
    payload = request.get_json(silent=True) or {}
    pdf_bytes = build_pdf(payload.get("profile", {}), payload.get("result", {}))
    response = app.response_class(pdf_bytes, mimetype="application/pdf")
    response.headers["Content-Disposition"] = "attachment; filename=grant-match-report.pdf"
    return response


def report_download(filename: str, content: bytes, mimetype: str):
    response = app.response_class(content, mimetype=mimetype)
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@app.post("/report/xlsx")
def xlsx_report():
    payload = request.get_json(silent=True) or {}
    return report_download("grant-match-report.xlsx", build_xlsx(payload.get("profile", {}), payload.get("result", {})), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.post("/report/docx")
def docx_report():
    payload = request.get_json(silent=True) or {}
    return report_download("grant-match-report.docx", build_docx(payload.get("profile", {}), payload.get("result", {})), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


if __name__ == "__main__":
    app.run(debug=True)
