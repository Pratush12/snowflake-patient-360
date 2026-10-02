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
    st.session_state.page = "patients"
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
    if st.button("📋 Patient List"):
        nav_to("patients")
    if st.button("💊 Drug Safety (CTGOV)"):
        nav_to("adverse_effects")
    if st.button("💬 Copilot Chat"):
        nav_to("copilot")
    st.markdown("---")
    st.caption("All data is fully synthetic and de-identified.\nIncludes CTGOV adverse effects data.")


# ============================================================
# PAGE: Patient List / Risk Stratification
# ============================================================
if st.session_state.page == "patients":
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
# PAGE: Patient 360 Detail
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

            # Demographics
            st.subheader("Demographics")
            d1, d2, d3, d4, d5 = st.columns(5)
            d1.metric("DOB", str(p["DATE_OF_BIRTH"]))
            d2.metric("Gender", p["GENDER"])
            d3.metric("Insurance", p["INSURANCE_TYPE"])
            d4.metric("Payer", p["INSURANCE_PAYER"])
            d5.metric("PCP", p["PCP_NAME"])

            # Risk scores
            if p["RISK_TIER"]:
                st.subheader("Risk Assessment")
                r1, r2, r3, r4 = st.columns(4)
                r1.metric("HCC Score", f"{p['HCC_SCORE']:.2f}" if p["HCC_SCORE"] else "-")
                r2.metric("Readmission Risk", f"{p['READMISSION_RISK']:.0f}%" if p["READMISSION_RISK"] else "-")
                r3.metric("Fall Risk", f"{p['FALL_RISK']:.0f}%" if p["FALL_RISK"] else "-")
                r4.metric("Med Adherence", f"{p['MEDICATION_ADHERENCE_SCORE']:.0f}%" if p["MEDICATION_ADHERENCE_SCORE"] else "-")
                if p["RISK_FACTORS"]:
                    st.info(f"**Risk Factors:** {p['RISK_FACTORS']}")

            # Claims summary
            total_billed = sum(c["BILLED_AMOUNT"] for c in claims)
            total_paid = sum(c["PAID_AMOUNT"] for c in claims)
            st.subheader("Claims Summary")
            cs1, cs2, cs3, cs4 = st.columns(4)
            cs1.metric("Total Billed", f"${total_billed:,.0f}")
            cs2.metric("Total Paid", f"${total_paid:,.0f}")
            cs3.metric("Encounters", len(encounters))
            cs4.metric("Diagnoses", len(diagnoses))

            # Tabbed data
            tab_enc, tab_dx, tab_med, tab_lab, tab_clm = st.tabs(
                ["Encounters", "Diagnoses", "Medications", "Labs", "Claims"]
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
            with tab_lab:
                df = to_df(labs)
                if len(df):
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No labs.")
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

    # Process pending user message
    if st.session_state.chat_history and st.session_state.chat_history[-1]["role"] == "user":
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

    # Text input for questions
    user_input = st.text_input("Ask a clinical or regulatory question...", key="chat_input")
    if st.button("Send") and user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        _rerun()
