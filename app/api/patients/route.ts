import { querySnowflake } from "@/lib/snowflake"
import { HC_DB, HC_SCHEMA } from "@/lib/constants"

export const dynamic = "force-dynamic"

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url)
    const search = searchParams.get("search") || ""

    let sql = `
      SELECT p.PATIENT_ID, p.FIRST_NAME, p.LAST_NAME,
             p.DATE_OF_BIRTH, p.GENDER, p.INSURANCE_TYPE, p.INSURANCE_PAYER,
             p.PCP_NAME, p.STATE,
             r.RISK_TIER, r.HCC_SCORE, r.READMISSION_RISK,
             r.MEDICATION_ADHERENCE_SCORE, r.RISK_FACTORS
      FROM ${HC_DB}.${HC_SCHEMA}.PATIENTS p
      LEFT JOIN ${HC_DB}.${HC_SCHEMA}.RISK_SCORES r ON p.PATIENT_ID = r.PATIENT_ID
    `
    const binds: string[] = []

    if (search) {
      sql += ` WHERE LOWER(p.FIRST_NAME || ' ' || p.LAST_NAME) LIKE LOWER(?) OR p.PATIENT_ID LIKE UPPER(?)`
      binds.push(`%${search}%`, `%${search}%`)
    }

    sql += ` ORDER BY r.HCC_SCORE DESC NULLS LAST LIMIT 50`

    const rows = await querySnowflake(sql, binds.length ? { binds } : undefined)

    const patients = (rows as Record<string, unknown>[]).map((r) => ({
      patientId: String(r.PATIENT_ID),
      firstName: String(r.FIRST_NAME),
      lastName: String(r.LAST_NAME),
      dob: r.DATE_OF_BIRTH instanceof Date ? r.DATE_OF_BIRTH.toISOString().slice(0, 10) : String(r.DATE_OF_BIRTH ?? ""),
      gender: String(r.GENDER),
      insuranceType: String(r.INSURANCE_TYPE),
      insurancePayer: String(r.INSURANCE_PAYER),
      pcpName: String(r.PCP_NAME),
      state: String(r.STATE),
      riskTier: r.RISK_TIER ? String(r.RISK_TIER) : null,
      hccScore: r.HCC_SCORE != null ? Number(r.HCC_SCORE) : null,
      readmissionRisk: r.READMISSION_RISK != null ? Number(r.READMISSION_RISK) : null,
      medAdherence: r.MEDICATION_ADHERENCE_SCORE != null ? Number(r.MEDICATION_ADHERENCE_SCORE) : null,
      riskFactors: r.RISK_FACTORS ? String(r.RISK_FACTORS) : null,
    }))

    return Response.json(patients)
  } catch (e) {
    console.error(new Date().toISOString(), "[patients]", e)
    return Response.json({ error: e instanceof Error ? e.message : "Failed to load patients" }, { status: 500 })
  }
}
