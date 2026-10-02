import { querySnowflake } from "@/lib/snowflake"
import { HC_DB, HC_SCHEMA } from "@/lib/constants"

export const dynamic = "force-dynamic"

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url)
    const patientId = searchParams.get("id")
    if (!patientId) return Response.json({ error: "Missing patient id" }, { status: 400 })

    const [patients, encounters, diagnoses, medications, labs, claims] = await Promise.all([
      querySnowflake(
        `SELECT * FROM ${HC_DB}.${HC_SCHEMA}.PATIENTS p
         LEFT JOIN ${HC_DB}.${HC_SCHEMA}.RISK_SCORES r ON p.PATIENT_ID = r.PATIENT_ID
         WHERE p.PATIENT_ID = ?`,
        { binds: [patientId] }
      ),
      querySnowflake(
        `SELECT ENCOUNTER_ID, ENCOUNTER_DATE, ENCOUNTER_TYPE, DEPARTMENT,
                PROVIDER_NAME, CHIEF_COMPLAINT, DISPOSITION, FACILITY
         FROM ${HC_DB}.${HC_SCHEMA}.ENCOUNTERS
         WHERE PATIENT_ID = ? ORDER BY ENCOUNTER_DATE DESC LIMIT 20`,
        { binds: [patientId] }
      ),
      querySnowflake(
        `SELECT DISTINCT d.ICD10_CODE, d.DESCRIPTION, d.CATEGORY, d.IS_CHRONIC
         FROM ${HC_DB}.${HC_SCHEMA}.DIAGNOSES d
         WHERE d.PATIENT_ID = ?
         ORDER BY d.IS_CHRONIC DESC, d.CATEGORY`,
        { binds: [patientId] }
      ),
      querySnowflake(
        `SELECT DRUG_NAME, GENERIC_NAME, DOSAGE, ROUTE, FREQUENCY, DRUG_CLASS, IS_ACTIVE, PRESCRIBER
         FROM ${HC_DB}.${HC_SCHEMA}.MEDICATIONS
         WHERE PATIENT_ID = ?
         ORDER BY IS_ACTIVE DESC, DRUG_NAME`,
        { binds: [patientId] }
      ),
      querySnowflake(
        `SELECT TEST_NAME, VALUE_NUMERIC, UNIT, FLAG, RESULT_DATE
         FROM ${HC_DB}.${HC_SCHEMA}.LAB_RESULTS
         WHERE PATIENT_ID = ?
         ORDER BY RESULT_DATE DESC LIMIT 30`,
        { binds: [patientId] }
      ),
      querySnowflake(
        `SELECT CLAIM_TYPE, BILLED_AMOUNT, PAID_AMOUNT, PATIENT_RESPONSIBILITY, STATUS, SERVICE_DATE, CPT_CODE
         FROM ${HC_DB}.${HC_SCHEMA}.CLAIMS
         WHERE PATIENT_ID = ?
         ORDER BY SERVICE_DATE DESC LIMIT 20`,
        { binds: [patientId] }
      ),
    ])

    function toIso(val: unknown): string | null {
      if (!val) return null
      if (val instanceof Date) return val.toISOString()
      return String(val)
    }

    const p = (patients as Record<string, unknown>[])[0]
    if (!p) return Response.json({ error: "Patient not found" }, { status: 404 })

    return Response.json({
      patient: {
        patientId: String(p.PATIENT_ID),
        firstName: String(p.FIRST_NAME),
        lastName: String(p.LAST_NAME),
        dob: toIso(p.DATE_OF_BIRTH)?.slice(0, 10),
        gender: String(p.GENDER),
        race: String(p.RACE),
        state: String(p.STATE),
        insuranceType: String(p.INSURANCE_TYPE),
        insurancePayer: String(p.INSURANCE_PAYER),
        pcpName: String(p.PCP_NAME),
        language: String(p.LANGUAGE),
        riskTier: p.RISK_TIER ? String(p.RISK_TIER) : null,
        hccScore: p.HCC_SCORE != null ? Number(p.HCC_SCORE) : null,
        readmissionRisk: p.READMISSION_RISK != null ? Number(p.READMISSION_RISK) : null,
        fallRisk: p.FALL_RISK != null ? Number(p.FALL_RISK) : null,
        medAdherence: p.MEDICATION_ADHERENCE_SCORE != null ? Number(p.MEDICATION_ADHERENCE_SCORE) : null,
        riskFactors: p.RISK_FACTORS ? String(p.RISK_FACTORS) : null,
      },
      encounters: (encounters as Record<string, unknown>[]).map((r) => ({
        id: String(r.ENCOUNTER_ID),
        date: toIso(r.ENCOUNTER_DATE)?.slice(0, 10),
        type: String(r.ENCOUNTER_TYPE),
        department: String(r.DEPARTMENT),
        provider: String(r.PROVIDER_NAME),
        complaint: String(r.CHIEF_COMPLAINT),
        disposition: String(r.DISPOSITION),
        facility: String(r.FACILITY),
      })),
      diagnoses: (diagnoses as Record<string, unknown>[]).map((r) => ({
        code: String(r.ICD10_CODE),
        description: String(r.DESCRIPTION),
        category: String(r.CATEGORY),
        isChronic: Boolean(r.IS_CHRONIC),
      })),
      medications: (medications as Record<string, unknown>[]).map((r) => ({
        drugName: String(r.DRUG_NAME),
        genericName: String(r.GENERIC_NAME),
        dosage: String(r.DOSAGE),
        route: String(r.ROUTE),
        frequency: String(r.FREQUENCY),
        drugClass: String(r.DRUG_CLASS),
        isActive: Boolean(r.IS_ACTIVE),
        prescriber: String(r.PRESCRIBER),
      })),
      labs: (labs as Record<string, unknown>[]).map((r) => ({
        testName: String(r.TEST_NAME),
        value: r.VALUE_NUMERIC != null ? Number(r.VALUE_NUMERIC) : null,
        unit: String(r.UNIT),
        flag: String(r.FLAG),
        date: toIso(r.RESULT_DATE)?.slice(0, 10),
      })),
      claims: (claims as Record<string, unknown>[]).map((r) => ({
        type: String(r.CLAIM_TYPE),
        billed: Number(r.BILLED_AMOUNT),
        paid: Number(r.PAID_AMOUNT),
        patientResp: Number(r.PATIENT_RESPONSIBILITY),
        status: String(r.STATUS),
        date: toIso(r.SERVICE_DATE)?.slice(0, 10),
        cpt: String(r.CPT_CODE),
      })),
    })
  } catch (e) {
    console.error(new Date().toISOString(), "[patient-detail]", e)
    return Response.json({ error: e instanceof Error ? e.message : "Failed to load patient" }, { status: 500 })
  }
}
