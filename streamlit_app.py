import streamlit as st
import json
import pandas as pd
from snowflake.snowpark.context import get_active_session

st.set_page_config(page_title="Patient 360 Copilot", page_icon="🏥", layout="wide")

_rerun = getattr(st, "rerun", None) or getattr(st, "experimental_rerun")

session = get_active_session()

HC_DB = "HEALTHCARE_COPILOT"
HC_SCHEMA = "CORE"
AGENT_FQN = f"{HC_DB}.{HC_SCHEMA}.PATIENT_COPILOT"


def run_query(sql):
    return session.sql(sql).collect()


def get_patients(search=""):
    where = ""
    if search:
        where = f"WHERE LOWER(p.FIRST_NAME || ' ' || p.LAST_NAME) LIKE LOWER('%{search}%') OR p.PATIENT_ID LIKE UPPER('%{search}%')"
    sql = f"""
        SELECT p.PATIENT_ID, p.FIRST_NAME, p.LAST_NAME, p.DATE_OF_BIRTH, p.GENDER,
               p.INSURANCE_TYPE, p.INSURANCE_PAYER, p.PCP_NAME, p.STATE,
               r.RISK_TIER, r.HCC_SCORE, r.READMISSION_RISK, r.MEDICATION_ADHERENCE_SCORE, r.RISK_FACTORS
        FROM {HC_DB}.{HC_SCHEMA}.PATIENTS p
        LEFT JOIN {HC_DB}.{HC_SCHEMA}.RISK_SCORES r ON p.PATIENT_ID = r.PATIENT_ID
        {where}
        ORDER BY r.HCC_SCORE DESC NULLS LAST LIMIT 50
    """
    return run_query(sql)


def get_patient_detail(patient_id):
    patient = run_query(f"""
        SELECT p.*, r.RISK_TIER, r.HCC_SCORE, r.READMISSION_RISK, r.FALL_RISK,
               r.MEDICATION_ADHERENCE_SCORE, r.ED_UTILIZATION_SCORE, r.RISK_FACTORS
        FROM {HC_DB}.{HC_SCHEMA}.PATIENTS p
        LEFT JOIN {HC_DB}.{HC_SCHEMA}.RISK_SCORES r ON p.PATIENT_ID = r.PATIENT_ID
        WHERE p.PATIENT_ID = '{patient_id}'
    """)
    encounters = run_query(f"""
        SELECT ENCOUNTER_ID, ENCOUNTER_DATE, ENCOUNTER_TYPE, DEPARTMENT,
               PROVIDER_NAME, CHIEF_COMPLAINT, DISPOSITION, FACILITY
        FROM {HC_DB}.{HC_SCHEMA}.ENCOUNTERS
        WHERE PATIENT_ID = '{patient_id}' ORDER BY ENCOUNTER_DATE DESC LIMIT 20
    """)
    diagnoses = run_query(f"""
        SELECT DISTINCT ICD10_CODE, DESCRIPTION, CATEGORY, IS_CHRONIC
        FROM {HC_DB}.{HC_SCHEMA}.DIAGNOSES
        WHERE PATIENT_ID = '{patient_id}' ORDER BY IS_CHRONIC DESC, CATEGORY
    """)
    medications = run_query(f"""
        SELECT DRUG_NAME, GENERIC_NAME, DOSAGE, ROUTE, FREQUENCY, DRUG_CLASS, IS_ACTIVE, PRESCRIBER
        FROM {HC_DB}.{HC_SCHEMA}.MEDICATIONS
        WHERE PATIENT_ID = '{patient_id}' ORDER BY IS_ACTIVE DESC, DRUG_NAME
    """)
    labs = run_query(f"""
        SELECT TEST_NAME, VALUE_NUMERIC, UNIT, FLAG, RESULT_DATE
        FROM {HC_DB}.{HC_SCHEMA}.LAB_RESULTS
        WHERE PATIENT_ID = '{patient_id}' ORDER BY RESULT_DATE DESC LIMIT 30
    """)
    claims = run_query(f"""
        SELECT CLAIM_TYPE, BILLED_AMOUNT, PAID_AMOUNT, PATIENT_RESPONSIBILITY, STATUS, SERVICE_DATE, CPT_CODE
        FROM {HC_DB}.{HC_SCHEMA}.CLAIMS
        WHERE PATIENT_ID = '{patient_id}' ORDER BY SERVICE_DATE DESC LIMIT 20
    """)
    return patient, encounters, diagnoses, medications, labs, claims


def call_agent(question, patient_id=None):
    user_text = question
    if patient_id:
        user_text = f"[Context: Patient ID is {patient_id}] {question}"
    messages = [{"role": "user", "content": [{"type": "text", "text": user_text}]}]
    payload = json.dumps({"messages": messages})
    result = run_query(f"""
        SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
            '{AGENT_FQN}',
            $${payload}$$,
            TRUE
        ) AS response
    """)
    if not result:
        return "No response from agent.", []
    raw = result[0]["RESPONSE"]
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return str(raw), []
    content = parsed.get("content", [])
    text = ""
    citations = []
    for item in content:
        if item.get("type") == "text":
            text += item.get("text", "")
            for ann in item.get("annotations", []):
                citations.append({
                    "title": ann.get("doc_title", ""),
                    "text": ann.get("text", ""),
                })
    return text or "No text response.", citations


def to_df(rows):
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([r.as_dict() for r in rows])


# --- Navigation ---
if "page" not in st.session_state:
    st.session_state.page = "home"
if "selected_patient" not in st.session_state:
    st.session_state.selected_patient = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


def nav_to(page, patient_id=None):
    st.session_state.page = page
    if patient_id:
        st.session_state.selected_patient = patient_id


# --- SIDEBAR ---
with st.sidebar:
    st.title("🏥 Patient 360 Copilot")
    st.caption("Unified EHR, claims & clinical document intelligence")
    st.markdown("---")
    if st.button("🏠 Home"):
        nav_to("home")
    if st.button("📋 Patient List"):
        nav_to("patients")
    if st.button("💊 Drug Safety (CTGOV)"):
        nav_to("adverse_effects")
    if st.button("💬 Copilot Chat"):
        nav_to("copilot")
    st.markdown("---")
    st.caption("All data is fully synthetic and de-identified.\nIncludes CTGOV adverse effects data.")


# ============================================================
# PAGE: Home — Landing Page with Features
# ============================================================
if st.session_state.page == "home":

    # CSS animations
    st.markdown("""
    <style>
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(30px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeInLeft {
        from { opacity: 0; transform: translateX(-30px); }
        to { opacity: 1; transform: translateX(0); }
    }
    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
    }
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .hero-title {
        font-size: 2.8em;
        font-weight: 700;
        animation: fadeInUp 0.8s ease-out;
        background: linear-gradient(135deg, #0f766e, #14b8a6, #0ea5e9);
        background-size: 200% 200%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: fadeInUp 0.8s ease-out, gradientShift 4s ease infinite;
    }
    .hero-subtitle {
        font-size: 1.3em;
        color: #64748b;
        animation: fadeInUp 1.0s ease-out;
        margin-bottom: 1.5em;
    }
    .feature-card {
        background: linear-gradient(135deg, #f0fdfa, #f0f9ff);
        border: 1px solid #ccfbf1;
        border-radius: 12px;
        padding: 24px;
        margin: 8px 0;
        animation: fadeInLeft 0.6s ease-out;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .feature-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 25px rgba(15, 118, 110, 0.15);
    }
    .feature-icon {
        font-size: 2.2em;
        margin-bottom: 8px;
    }
    .feature-title {
        font-size: 1.15em;
        font-weight: 600;
        color: #0f172a;
        margin-bottom: 6px;
    }
    .feature-desc {
        font-size: 0.92em;
        color: #475569;
        line-height: 1.5;
    }
    .stat-box {
        text-align: center;
        padding: 20px;
        background: linear-gradient(135deg, #0f766e, #14b8a6);
        border-radius: 12px;
        color: white;
        animation: fadeInUp 1.2s ease-out;
    }
    .stat-number {
        font-size: 2em;
        font-weight: 700;
    }
    .stat-label {
        font-size: 0.85em;
        opacity: 0.9;
    }
    .tech-badge {
        display: inline-block;
        background: #f1f5f9;
        border: 1px solid #e2e8f0;
        border-radius: 20px;
        padding: 6px 14px;
        margin: 4px;
        font-size: 0.85em;
        color: #334155;
        animation: fadeInUp 1.4s ease-out;
    }
    .cta-button {
        display: inline-block;
        background: linear-gradient(135deg, #0f766e, #14b8a6);
        color: white !important;
        padding: 12px 32px;
        border-radius: 8px;
        font-size: 1.1em;
        font-weight: 600;
        text-decoration: none;
        animation: fadeInUp 1.0s ease-out, pulse 2s ease-in-out 2s infinite;
        margin: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

    # Hero Section
    st.markdown('<div class="hero-title">Patient 360 Healthcare Copilot</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">Unifying EHR records, clinical documents, insurance claims, and clinical trial safety data into one intelligent interface with cited, evidence-based answers.</div>', unsafe_allow_html=True)

    # CTA Buttons
    col_cta1, col_cta2, col_cta3, _ = st.columns([1, 1, 1, 1])
    with col_cta1:
        if st.button("📋 Explore Patients", key="cta_patients"):
            nav_to("patients")
            _rerun()
    with col_cta2:
        if st.button("💬 Try the Copilot", key="cta_copilot"):
            nav_to("copilot")
            _rerun()
    with col_cta3:
        if st.button("💊 Drug Safety", key="cta_safety"):
            nav_to("adverse_effects")
            _rerun()

    st.markdown("---")

    # Data Stats
    st.markdown("### By the Numbers")
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.markdown('<div class="stat-box"><div class="stat-number">50</div><div class="stat-label">Patients</div></div>', unsafe_allow_html=True)
    s2.markdown('<div class="stat-box"><div class="stat-number">3,238</div><div class="stat-label">Structured Records</div></div>', unsafe_allow_html=True)
    s3.markdown('<div class="stat-box"><div class="stat-number">228</div><div class="stat-label">Clinical Documents</div></div>', unsafe_allow_html=True)
    s4.markdown('<div class="stat-box"><div class="stat-number">40</div><div class="stat-label">CTGOV Adverse Events</div></div>', unsafe_allow_html=True)
    s5.markdown('<div class="stat-box"><div class="stat-number">8</div><div class="stat-label">Data Tables</div></div>', unsafe_allow_html=True)

    st.markdown("")

    # Feature Cards
    st.markdown("### What This App Does")

    f1, f2 = st.columns(2)
    with f1:
        st.markdown("""
        <div class="feature-card" style="animation-delay: 0.1s">
            <div class="feature-icon">🩺</div>
            <div class="feature-title">Patient 360 View</div>
            <div class="feature-desc">Complete patient profile with demographics, encounters, diagnoses, medications, lab results, claims, and risk scores — all in one dashboard with interactive charts and a visual patient journey timeline.</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="feature-card" style="animation-delay: 0.3s">
            <div class="feature-icon">🤖</div>
            <div class="feature-title">AI Copilot with Cited Evidence</div>
            <div class="feature-desc">Ask questions in plain language. The copilot searches both structured data and clinical documents, returning answers with cited sources — never opaque predictions. Powered by Snowflake Cortex Agent.</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="feature-card" style="animation-delay: 0.5s">
            <div class="feature-icon">📊</div>
            <div class="feature-title">Risk Stratification</div>
            <div class="feature-desc">Every patient scored with HCC, readmission risk, fall risk, and medication adherence. Filter by risk tier to prioritize care interventions for the most vulnerable patients.</div>
        </div>
        """, unsafe_allow_html=True)

    with f2:
        st.markdown("""
        <div class="feature-card" style="animation-delay: 0.2s">
            <div class="feature-icon">📄</div>
            <div class="feature-title">Clinical Document Intelligence</div>
            <div class="feature-desc">228 clinical documents — physician notes, discharge summaries, radiology reports, FDA safety alerts, and clinical guidelines — indexed for semantic search with source citations.</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="feature-card" style="animation-delay: 0.4s">
            <div class="feature-icon">💊</div>
            <div class="feature-title">CTGOV Drug Safety Integration</div>
            <div class="feature-desc">Adverse effects from ClinicalTrials.gov linked to patient medications. Check any patient's active drugs against trial-reported side effects with frequency rates and serious event flags.</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="feature-card" style="animation-delay: 0.6s">
            <div class="feature-icon">🧠</div>
            <div class="feature-title">AI Patient Summary</div>
            <div class="feature-desc">Every patient 360 opens with an AI-generated clinical summary — a concise paragraph covering conditions, medications, risk level, and next-visit priorities. Built for new doctors taking over care.</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Architecture / Tech Stack
    st.markdown("### Built On Snowflake")
    st.markdown("""
    <div style="text-align: center; animation: fadeInUp 1.4s ease-out;">
        <span class="tech-badge">Cortex Agent</span>
        <span class="tech-badge">Cortex Analyst</span>
        <span class="tech-badge">Cortex Search</span>
        <span class="tech-badge">Cortex LLM</span>
        <span class="tech-badge">Semantic View</span>
        <span class="tech-badge">Streamlit-in-Snowflake</span>
        <span class="tech-badge">CTGOV Data</span>
        <span class="tech-badge">Synthetic EHR</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")
    st.markdown("""
    <div style="text-align: center; color: #64748b; animation: fadeInUp 1.6s ease-out; margin-top: 1em;">
        <em>All data is fully synthetic and de-identified. No real patient information is used.</em>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# PAGE: Patient List / Risk Stratification
# ============================================================
elif st.session_state.page == "patients":
    st.header("Patient Risk Stratification")

    patients = get_patients()

    tier_counts = {"Critical": 0, "High": 0, "Moderate": 0, "Low": 0}
    for p in patients:
        tier = p["RISK_TIER"]
        if tier in tier_counts:
            tier_counts[tier] += 1

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 Critical Risk", tier_counts["Critical"])
    c2.metric("🟠 High Risk", tier_counts["High"])
    c3.metric("🟡 Moderate Risk", tier_counts["Moderate"])
    c4.metric("🟢 Low Risk", tier_counts["Low"])

    search = st.text_input("Search by name or patient ID")
    if search:
        patients = get_patients(search)

    filter_tier = st.selectbox("Filter by risk tier", ["All", "Critical", "High", "Moderate", "Low"])

    # Build patient table
    table_data = []
    for p in patients:
        tier = p["RISK_TIER"] or "Unknown"
        if filter_tier != "All" and tier != filter_tier:
            continue
        hcc = p["HCC_SCORE"]
        readmit = p["READMISSION_RISK"]
        table_data.append({
            "Patient ID": p["PATIENT_ID"],
            "Name": f"{p['FIRST_NAME']} {p['LAST_NAME']}",
            "Gender": p["GENDER"],
            "Insurance": p["INSURANCE_TYPE"],
            "PCP": p["PCP_NAME"],
            "Risk Tier": tier,
            "HCC Score": f"{hcc:.2f}" if hcc else "-",
            "Readmit %": f"{readmit:.0f}%" if readmit else "-",
        })

    st.subheader(f"Patients ({len(table_data)})")
    if table_data:
        st.dataframe(pd.DataFrame(table_data), use_container_width=True)

    st.markdown("---")
    st.subheader("View Patient Detail")
    patient_ids = [p["PATIENT_ID"] for p in patients]
    selected = st.selectbox("Select a patient", patient_ids if patient_ids else ["No patients"])
    col_view, col_ask = st.columns(2)
    if col_view.button("View Patient 360"):
        nav_to("patient_detail", selected)
        _rerun()
    if col_ask.button("Ask Copilot About Patient"):
        nav_to("copilot", selected)
        _rerun()


# ============================================================
# PAGE: Patient 360 Detail — Dashboard with Patient Journey
# ============================================================
elif st.session_state.page == "patient_detail":
    pid = st.session_state.selected_patient
    if not pid:
        st.warning("No patient selected.")
        if st.button("Back to Patient List"):
            nav_to("patients")
            _rerun()
    else:
        patient, encounters, diagnoses, medications, labs, claims = get_patient_detail(pid)
        if not patient:
            st.error("Patient not found.")
        else:
            p = patient[0]
            if st.button("← Back to Patient List"):
                nav_to("patients")
                _rerun()

            tier = p["RISK_TIER"] or "Unknown"
            st.header(f"{p['FIRST_NAME']} {p['LAST_NAME']} ({pid})")
            st.markdown(f"**Risk Tier: {tier}**")

            if st.button("💬 Ask Copilot About This Patient"):
                nav_to("copilot", pid)
                _rerun()

            # ============================================================
            # AI PATIENT SUMMARY — for new doctors at a glance
            # ============================================================
            st.subheader("📋 Patient Summary")
            chronic_list = ", ".join(d["DESCRIPTION"] for d in diagnoses if d["IS_CHRONIC"])
            active_med_list = ", ".join(f"{m['DRUG_NAME']} {m['DOSAGE']}" for m in medications if m["IS_ACTIVE"])
            abnormal_list = ", ".join(f"{l['TEST_NAME']}={l['VALUE_NUMERIC']} {l['UNIT']} ({l['FLAG']})"
                                      for l in labs if l["FLAG"] != "Normal")[:500]
            recent_enc = encounters[0] if encounters else None
            recent_str = (f"Most recent visit: {recent_enc['ENCOUNTER_TYPE']} on {recent_enc['ENCOUNTER_DATE']} "
                          f"for {recent_enc['CHIEF_COMPLAINT']} ({recent_enc['DISPOSITION']})") if recent_enc else "No recent encounters."

            hcc = p["HCC_SCORE"] if p["HCC_SCORE"] is not None else "N/A"
            readmit = p["READMISSION_RISK"] if p["READMISSION_RISK"] is not None else "N/A"
            med_adh = p["MEDICATION_ADHERENCE_SCORE"] if p["MEDICATION_ADHERENCE_SCORE"] is not None else "N/A"
            risk_factors = p["RISK_FACTORS"] if p["RISK_FACTORS"] is not None else "None noted"

            summary_prompt = f"""You are a clinical summarizer. Write a concise 4-5 sentence patient summary for a new doctor taking over care. Include:
1. Patient basics (age, gender, insurance)
2. Key chronic conditions and risk level
3. Current active medications (highlight any polypharmacy concerns)
4. Recent clinical activity and any flags (abnormal labs, high risk scores)
5. One sentence on what to prioritize in the next visit.

Patient: {p['FIRST_NAME']} {p['LAST_NAME']}, {p['GENDER']}, DOB {p['DATE_OF_BIRTH']}, {p['INSURANCE_TYPE']} ({p['INSURANCE_PAYER']})
Risk Tier: {tier}, HCC Score: {hcc}, Readmission Risk: {readmit}%, Med Adherence: {med_adh}%
Risk Factors: {risk_factors}
Chronic Conditions: {chronic_list or 'None documented'}
Active Medications: {active_med_list or 'None'}
Abnormal Labs: {abnormal_list or 'None'}
{recent_str}
Total Encounters: {len(encounters)}, Total Claims Billed: ${sum(c['BILLED_AMOUNT'] for c in claims):,.0f}

Write the summary in plain clinical language. Do not use bullet points. This is synthetic data."""

            summary_key = f"summary_{pid}"
            if summary_key not in st.session_state:
                with st.spinner("Generating patient summary..."):
                    try:
                        result = run_query(f"""
                            SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-8b', $${summary_prompt}$$) AS summary
                        """)
                        st.session_state[summary_key] = result[0]["SUMMARY"] if result else "Summary unavailable."
                    except Exception as e:
                        st.session_state[summary_key] = f"Could not generate summary: {e}"

            st.info(st.session_state[summary_key])
            st.markdown("---")

            # ---- ROW 1: Demographics ----
            st.subheader("Demographics")
            d1, d2, d3, d4, d5 = st.columns(5)
            d1.metric("DOB", str(p["DATE_OF_BIRTH"]))
            d2.metric("Gender", p["GENDER"])
            d3.metric("Insurance", p["INSURANCE_TYPE"])
            d4.metric("Payer", p["INSURANCE_PAYER"])
            d5.metric("PCP", p["PCP_NAME"])

            # ---- ROW 2: Risk Scores ----
            if p["RISK_TIER"]:
                st.subheader("Risk Assessment")
                r1, r2, r3, r4 = st.columns(4)
                r1.metric("HCC Score", f"{p['HCC_SCORE']:.2f}" if p["HCC_SCORE"] else "-")
                r2.metric("Readmission Risk", f"{p['READMISSION_RISK']:.0f}%" if p["READMISSION_RISK"] else "-")
                r3.metric("Fall Risk", f"{p['FALL_RISK']:.0f}%" if p["FALL_RISK"] else "-")
                r4.metric("Med Adherence", f"{p['MEDICATION_ADHERENCE_SCORE']:.0f}%" if p["MEDICATION_ADHERENCE_SCORE"] else "-")
                if p["RISK_FACTORS"]:
                    st.info(f"**Risk Factors:** {p['RISK_FACTORS']}")

            # ---- ROW 3: Key Metrics ----
            total_billed = sum(c["BILLED_AMOUNT"] for c in claims)
            total_paid = sum(c["PAID_AMOUNT"] for c in claims)
            active_meds = [m for m in medications if m["IS_ACTIVE"]]
            chronic_dx = [d for d in diagnoses if d["IS_CHRONIC"]]
            abnormal_labs = [l for l in labs if l["FLAG"] != "Normal"]
            st.subheader("Key Metrics")
            k1, k2, k3, k4, k5, k6 = st.columns(6)
            k1.metric("Encounters", len(encounters))
            k2.metric("Diagnoses", len(diagnoses))
            k3.metric("Active Meds", len(active_meds))
            k4.metric("Abnormal Labs", len(abnormal_labs))
            k5.metric("Total Billed", f"${total_billed:,.0f}")
            k6.metric("Total Paid", f"${total_paid:,.0f}")

            st.markdown("---")

            # ============================================================
            # PATIENT JOURNEY TIMELINE
            # ============================================================
            st.subheader("📅 Patient Journey Timeline")
            if encounters:
                journey_df = to_df(encounters).sort_values("ENCOUNTER_DATE")
                # Show timeline as a table with visual indicators
                journey_display = []
                for _, row in journey_df.iterrows():
                    enc_type = str(row.get("ENCOUNTER_TYPE", ""))
                    icon = {"Emergency": "🚨", "Inpatient": "🏥", "Office Visit": "🩺",
                            "Telehealth": "📱", "Urgent Care": "⚡", "Lab Only": "🔬",
                            "Imaging": "📷", "Procedure": "🔧"}.get(enc_type, "📋")
                    journey_display.append({
                        "Date": str(row.get("ENCOUNTER_DATE", "")),
                        "Type": f"{icon} {enc_type}",
                        "Department": str(row.get("DEPARTMENT", "")),
                        "Chief Complaint": str(row.get("CHIEF_COMPLAINT", "")),
                        "Provider": str(row.get("PROVIDER_NAME", "")),
                        "Disposition": str(row.get("DISPOSITION", "")),
                        "Facility": str(row.get("FACILITY", "")),
                    })
                st.dataframe(pd.DataFrame(journey_display), use_container_width=True)

                # Encounters over time chart
                enc_by_month = journey_df.copy()
                enc_by_month["MONTH"] = pd.to_datetime(enc_by_month["ENCOUNTER_DATE"]).dt.to_period("M").astype(str)
                month_counts = enc_by_month.groupby("MONTH").size().reset_index(name="Encounters")
                st.caption("Encounters over time")
                st.bar_chart(month_counts.set_index("MONTH"))
            else:
                st.info("No encounters recorded.")

            st.markdown("---")

            # ============================================================
            # DASHBOARD CHARTS
            # ============================================================
            chart_left, chart_right = st.columns(2)

            with chart_left:
                # Encounter type breakdown
                st.subheader("Encounter Types")
                if encounters:
                    enc_df = to_df(encounters)
                    type_counts = enc_df["ENCOUNTER_TYPE"].value_counts().reset_index()
                    type_counts.columns = ["Type", "Count"]
                    st.bar_chart(type_counts.set_index("Type"))
                else:
                    st.info("No data.")

                # Diagnosis categories
                st.subheader("Diagnosis Categories")
                if diagnoses:
                    dx_df = to_df(diagnoses)
                    cat_counts = dx_df["CATEGORY"].value_counts().reset_index()
                    cat_counts.columns = ["Category", "Count"]
                    st.bar_chart(cat_counts.set_index("Category"))
                else:
                    st.info("No data.")

            with chart_right:
                # Medication classes
                st.subheader("Medication Classes")
                if medications:
                    med_df = to_df(medications)
                    class_counts = med_df["DRUG_CLASS"].value_counts().reset_index()
                    class_counts.columns = ["Drug Class", "Count"]
                    st.bar_chart(class_counts.set_index("Drug Class"))
                else:
                    st.info("No data.")

                # Claims by status
                st.subheader("Claims by Status")
                if claims:
                    clm_df = to_df(claims)
                    status_counts = clm_df["STATUS"].value_counts().reset_index()
                    status_counts.columns = ["Status", "Count"]
                    st.bar_chart(status_counts.set_index("Status"))
                else:
                    st.info("No data.")

            st.markdown("---")

            # ============================================================
            # LAB RESULTS TREND
            # ============================================================
            st.subheader("🔬 Lab Results")
            if labs:
                lab_df = to_df(labs)
                test_names = sorted(lab_df["TEST_NAME"].unique())
                selected_test = st.selectbox("Select lab test to view trend", test_names)
                filtered_lab = lab_df[lab_df["TEST_NAME"] == selected_test].sort_values("RESULT_DATE")
                if len(filtered_lab) > 1:
                    chart_data = filtered_lab[["RESULT_DATE", "VALUE_NUMERIC"]].copy()
                    chart_data = chart_data.rename(columns={"RESULT_DATE": "Date", "VALUE_NUMERIC": "Value"})
                    chart_data["Date"] = pd.to_datetime(chart_data["Date"])
                    st.line_chart(chart_data.set_index("Date"))
                st.dataframe(filtered_lab, use_container_width=True)
            else:
                st.info("No lab results.")

            st.markdown("---")

            # ============================================================
            # MEDICATION SAFETY (CTGOV Link)
            # ============================================================
            if active_meds:
                st.subheader("⚠️ Medication Safety — CTGOV Adverse Effects")
                drug_names = list(set(m["DRUG_NAME"] for m in active_meds))
                drug_list_sql = ",".join(f"'{d}'" for d in drug_names)
                safety_data = run_query(f"""
                    SELECT DRUG_NAME, ADVERSE_EVENT, ORGAN_SYSTEM, SEVERITY,
                           FREQUENCY_PCT, IS_SERIOUS, NCT_ID
                    FROM {HC_DB}.{HC_SCHEMA}.CTGOV_ADVERSE_EFFECTS
                    WHERE DRUG_NAME IN ({drug_list_sql})
                    ORDER BY IS_SERIOUS DESC, FREQUENCY_PCT DESC
                """)
                if safety_data:
                    serious = [r for r in safety_data if r["IS_SERIOUS"]]
                    if serious:
                        st.warning(f"⚠️ {len(serious)} serious adverse event(s) reported in CTGOV for this patient's active medications")
                    st.dataframe(to_df(safety_data), use_container_width=True)
                else:
                    st.success("No CTGOV adverse effects data for this patient's active medications.")

            st.markdown("---")

            # ============================================================
            # DETAILED TABS (same as before)
            # ============================================================
            st.subheader("Detailed Records")
            tab_enc, tab_dx, tab_med, tab_clm = st.tabs(
                ["Encounters", "Diagnoses", "Medications", "Claims"]
            )
            with tab_enc:
                df = to_df(encounters)
                if len(df):
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No encounters.")
            with tab_dx:
                df = to_df(diagnoses)
                if len(df):
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No diagnoses.")
            with tab_med:
                df = to_df(medications)
                if len(df):
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No medications.")
            with tab_clm:
                df = to_df(claims)
                if len(df):
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No claims.")


# ============================================================
# PAGE: CTGOV Adverse Effects / Drug Safety
# ============================================================
elif st.session_state.page == "adverse_effects":
    if st.button("← Back to Patient List"):
        nav_to("patients")
        _rerun()

    st.header("💊 CTGOV Drug Safety - Adverse Effects")
    st.caption("Adverse events from ClinicalTrials.gov (CTGOV) linked to patient medications")

    # Summary metrics
    ae_summary = run_query(f"""
        SELECT COUNT(DISTINCT AE_ID) AS total_ae,
               COUNT(DISTINCT DRUG_NAME) AS drugs_covered,
               COUNT(DISTINCT NCT_ID) AS trials,
               COUNT(DISTINCT CASE WHEN IS_SERIOUS THEN AE_ID END) AS serious_ae
        FROM {HC_DB}.{HC_SCHEMA}.CTGOV_ADVERSE_EFFECTS
    """)
    s = ae_summary[0]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Adverse Events", s["TOTAL_AE"])
    m2.metric("Drugs Covered", s["DRUGS_COVERED"])
    m3.metric("Clinical Trials", s["TRIALS"])
    m4.metric("Serious AEs", s["SERIOUS_AE"])

    st.markdown("---")

    # Drug filter
    drugs = run_query(f"SELECT DISTINCT DRUG_NAME FROM {HC_DB}.{HC_SCHEMA}.CTGOV_ADVERSE_EFFECTS ORDER BY DRUG_NAME")
    drug_list = ["All"] + [d["DRUG_NAME"] for d in drugs]
    selected_drug = st.selectbox("Filter by drug", drug_list)

    # Severity filter
    severity_filter = st.selectbox("Filter by severity", ["All", "Severe", "Moderate", "Mild"])

    where_clauses = []
    if selected_drug != "All":
        where_clauses.append(f"DRUG_NAME = '{selected_drug}'")
    if severity_filter != "All":
        where_clauses.append(f"SEVERITY = '{severity_filter}'")
    where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    ae_data = run_query(f"""
        SELECT DRUG_NAME, ADVERSE_EVENT, ORGAN_SYSTEM, SEVERITY,
               FREQUENCY_PCT, SUBJECTS_AFFECTED, SUBJECTS_AT_RISK,
               IS_SERIOUS, NCT_ID, TRIAL_PHASE, CONDITION_STUDIED
        FROM {HC_DB}.{HC_SCHEMA}.CTGOV_ADVERSE_EFFECTS
        {where}
        ORDER BY FREQUENCY_PCT DESC
    """)

    st.subheader(f"Adverse Events ({len(ae_data)} records)")
    if ae_data:
        df = to_df(ae_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No adverse events match the filter.")

    st.markdown("---")

    # Patient medication safety check
    st.subheader("🔍 Patient Medication Safety Check")
    st.caption("Select a patient to see CTGOV adverse effects for their active medications")

    patient_list = run_query(f"""
        SELECT PATIENT_ID, FIRST_NAME || ' ' || LAST_NAME AS NAME
        FROM {HC_DB}.{HC_SCHEMA}.PATIENTS ORDER BY PATIENT_ID
    """)
    patient_options = [f"{p['PATIENT_ID']} - {p['NAME']}" for p in patient_list]
    selected_patient_str = st.selectbox("Select patient", patient_options)
    check_pid = selected_patient_str.split(" - ")[0] if selected_patient_str else None

    if check_pid and st.button("Check Drug Safety"):
        safety_data = run_query(f"""
            SELECT m.DRUG_NAME, m.DOSAGE, m.DRUG_CLASS,
                   ae.ADVERSE_EVENT, ae.ORGAN_SYSTEM, ae.SEVERITY,
                   ae.FREQUENCY_PCT, ae.IS_SERIOUS, ae.NCT_ID, ae.TRIAL_TITLE
            FROM {HC_DB}.{HC_SCHEMA}.MEDICATIONS m
            JOIN {HC_DB}.{HC_SCHEMA}.CTGOV_ADVERSE_EFFECTS ae ON m.DRUG_NAME = ae.DRUG_NAME
            WHERE m.PATIENT_ID = '{check_pid}' AND m.IS_ACTIVE = TRUE
            ORDER BY ae.IS_SERIOUS DESC, ae.FREQUENCY_PCT DESC
        """)
        if safety_data:
            serious = [r for r in safety_data if r["IS_SERIOUS"]]
            if serious:
                st.warning(f"⚠️ {len(serious)} serious adverse event(s) reported for this patient's active medications")
            st.subheader(f"Adverse effects for {selected_patient_str}'s active medications")
            df = to_df(safety_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.success("No CTGOV adverse effects data found for this patient's active medications.")


# ============================================================
# PAGE: Copilot Chat
# ============================================================
elif st.session_state.page == "copilot":
    if st.button("← Back to Patient List"):
        nav_to("patients")
        _rerun()

    st.header("Healthcare Copilot")

    pid = st.session_state.selected_patient
    patient_scope = st.text_input("Patient scope (optional)", value=pid or "")

    st.markdown("**Ask about patients, clinical data, or regulatory guidelines.**")
    st.caption("Combines structured EHR/claims data with clinical documents for cited answers.")

    # Sample questions
    samples = [
        "What are the known adverse effects of Metformin from clinical trials?",
        "What are the FDA safety alerts about metformin?",
        "Show me patients with Critical risk tier",
        "For patient P-0001, what CTGOV adverse effects are linked to their medications?",
        "Which drugs have serious adverse events reported in CTGOV?",
        "What are the heart failure management guidelines?",
    ]
    sc1, sc2, sc3 = st.columns(3)
    for i, q in enumerate(samples):
        col = [sc1, sc2, sc3][i % 3]
        if col.button(q, key=f"sq_{i}"):
            st.session_state.chat_history.append({"role": "user", "content": q})
            _rerun()

    st.markdown("---")

    # Display chat history
    for msg in st.session_state.chat_history:
        role_label = "🧑 You" if msg["role"] == "user" else "🤖 Copilot"
        st.markdown(f"**{role_label}:** {msg['content']}")
        if "citations" in msg and msg["citations"]:
            with st.expander(f"📄 {len(msg['citations'])} source(s)"):
                for c in msg["citations"]:
                    st.markdown(f"**{c['title']}**")
                    excerpt = c["text"][:300] + "..." if len(c["text"]) > 300 else c["text"]
                    st.caption(excerpt)

    # Process pending user message (only if not already answered)
    if "pending_answered" not in st.session_state:
        st.session_state.pending_answered = set()

    if st.session_state.chat_history and st.session_state.chat_history[-1]["role"] == "user":
        msg_idx = len(st.session_state.chat_history) - 1
        if msg_idx not in st.session_state.pending_answered:
            last_q = st.session_state.chat_history[-1]["content"]
            with st.spinner("Thinking..."):
                text, citations = call_agent(last_q, patient_scope if patient_scope else None)
            st.markdown(f"**🤖 Copilot:** {text}")
            if citations:
                with st.expander(f"📄 {len(citations)} source(s)"):
                    for c in citations:
                        st.markdown(f"**{c['title']}**")
                        excerpt = c["text"][:300] + "..." if len(c["text"]) > 300 else c["text"]
                        st.caption(excerpt)
            st.session_state.chat_history.append({"role": "assistant", "content": text, "citations": citations})
            st.session_state.pending_answered.add(msg_idx)

    # Text input for questions
    user_input = st.text_input("Ask a clinical or regulatory question...", key="chat_input")
    if st.button("Send") and user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        _rerun()
