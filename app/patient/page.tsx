"use client"

import { useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import { Suspense } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import Link from "next/link"

const riskColors: Record<string, string> = {
  Critical: "bg-red-600 text-white",
  High: "bg-orange-500 text-white",
  Moderate: "bg-yellow-500 text-black",
  Low: "bg-green-600 text-white",
}

interface PatientDetail {
  patient: {
    patientId: string; firstName: string; lastName: string; dob: string
    gender: string; race: string; state: string; insuranceType: string
    insurancePayer: string; pcpName: string; language: string
    riskTier: string | null; hccScore: number | null
    readmissionRisk: number | null; fallRisk: number | null
    medAdherence: number | null; riskFactors: string | null
  }
  encounters: Array<{
    id: string; date: string; type: string; department: string
    provider: string; complaint: string; disposition: string; facility: string
  }>
  diagnoses: Array<{ code: string; description: string; category: string; isChronic: boolean }>
  medications: Array<{
    drugName: string; genericName: string; dosage: string; route: string
    frequency: string; drugClass: string; isActive: boolean; prescriber: string
  }>
  labs: Array<{ testName: string; value: number | null; unit: string; flag: string; date: string }>
  claims: Array<{
    type: string; billed: number; paid: number; patientResp: number
    status: string; date: string; cpt: string
  }>
}

function PatientContent() {
  const searchParams = useSearchParams()
  const patientId = searchParams.get("id")
  const [data, setData] = useState<PatientDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<"encounters" | "diagnoses" | "medications" | "labs" | "claims">("encounters")

  useEffect(() => {
    if (!patientId) return
    setLoading(true)
    fetch(`/api/patient?id=${encodeURIComponent(patientId)}`)
      .then((r) => r.json())
      .then(setData)
      .finally(() => setLoading(false))
  }, [patientId])

  if (!patientId) return <p className="p-8 text-muted-foreground">No patient selected.</p>
  if (loading) return <p className="p-8 text-muted-foreground">Loading patient data...</p>
  if (!data?.patient) return <p className="p-8 text-muted-foreground">Patient not found.</p>

  const p = data.patient
  const activeMeds = data.medications.filter((m) => m.isActive)
  const abnormalLabs = data.labs.filter((l) => l.flag !== "Normal")
  const totalBilled = data.claims.reduce((s, c) => s + c.billed, 0)
  const totalPaid = data.claims.reduce((s, c) => s + c.paid, 0)

  const tabs = ["encounters", "diagnoses", "medications", "labs", "claims"] as const

  return (
    <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/"><Button variant="outline" size="sm">Back</Button></Link>
        <h1 className="text-2xl font-semibold">{p.firstName} {p.lastName}</h1>
        <span className="text-muted-foreground font-mono text-sm">{p.patientId}</span>
        {p.riskTier && <Badge className={riskColors[p.riskTier]}>{p.riskTier} Risk</Badge>}
        <div className="ml-auto">
          <Link href={`/copilot?patient=${p.patientId}`}>
            <Button>Ask Copilot About This Patient</Button>
          </Link>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <Card><CardContent className="pt-4">
          <p className="text-xs text-muted-foreground">DOB</p>
          <p className="font-medium">{p.dob}</p>
        </CardContent></Card>
        <Card><CardContent className="pt-4">
          <p className="text-xs text-muted-foreground">Gender / Race</p>
          <p className="font-medium">{p.gender} / {p.race}</p>
        </CardContent></Card>
        <Card><CardContent className="pt-4">
          <p className="text-xs text-muted-foreground">Insurance</p>
          <p className="font-medium">{p.insuranceType}</p>
          <p className="text-xs text-muted-foreground">{p.insurancePayer}</p>
        </CardContent></Card>
        <Card><CardContent className="pt-4">
          <p className="text-xs text-muted-foreground">PCP</p>
          <p className="font-medium">{p.pcpName}</p>
        </CardContent></Card>
        <Card><CardContent className="pt-4">
          <p className="text-xs text-muted-foreground">Active Meds</p>
          <p className="text-xl font-bold">{activeMeds.length}</p>
        </CardContent></Card>
        <Card><CardContent className="pt-4">
          <p className="text-xs text-muted-foreground">Abnormal Labs</p>
          <p className="text-xl font-bold">{abnormalLabs.length}</p>
        </CardContent></Card>
      </div>

      {/* Risk scores */}
      {p.riskTier && (
        <Card>
          <CardHeader><CardTitle className="text-lg">Risk Assessment</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <div>
                <p className="text-xs text-muted-foreground">HCC Score</p>
                <p className="text-xl font-bold">{p.hccScore?.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Readmission Risk</p>
                <p className="text-xl font-bold">{p.readmissionRisk?.toFixed(0)}%</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Fall Risk</p>
                <p className="text-xl font-bold">{p.fallRisk?.toFixed(0)}%</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Med Adherence</p>
                <p className="text-xl font-bold">{p.medAdherence?.toFixed(0)}%</p>
              </div>
            </div>
            {p.riskFactors && (
              <p className="text-sm text-muted-foreground"><strong>Factors:</strong> {p.riskFactors}</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Claims summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card><CardContent className="pt-4">
          <p className="text-xs text-muted-foreground">Total Billed</p>
          <p className="text-lg font-bold">${totalBilled.toLocaleString()}</p>
        </CardContent></Card>
        <Card><CardContent className="pt-4">
          <p className="text-xs text-muted-foreground">Total Paid</p>
          <p className="text-lg font-bold">${totalPaid.toLocaleString()}</p>
        </CardContent></Card>
        <Card><CardContent className="pt-4">
          <p className="text-xs text-muted-foreground">Encounters</p>
          <p className="text-lg font-bold">{data.encounters.length}</p>
        </CardContent></Card>
        <Card><CardContent className="pt-4">
          <p className="text-xs text-muted-foreground">Diagnoses</p>
          <p className="text-lg font-bold">{data.diagnoses.length}</p>
        </CardContent></Card>
      </div>

      {/* Tabbed data */}
      <Card>
        <CardHeader>
          <div className="flex gap-2 flex-wrap">
            {tabs.map((t) => (
              <Button
                key={t}
                variant={tab === t ? "default" : "outline"}
                size="sm"
                onClick={() => setTab(t)}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </Button>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            {tab === "encounters" && (
              <table className="w-full text-sm">
                <thead><tr className="border-b text-left text-muted-foreground">
                  <th className="pb-2 pr-3">Date</th><th className="pb-2 pr-3">Type</th>
                  <th className="pb-2 pr-3">Dept</th><th className="pb-2 pr-3">Complaint</th>
                  <th className="pb-2 pr-3">Provider</th><th className="pb-2">Disposition</th>
                </tr></thead>
                <tbody>
                  {data.encounters.map((e) => (
                    <tr key={e.id} className="border-b"><td className="py-1.5 pr-3">{e.date}</td>
                      <td className="py-1.5 pr-3">{e.type}</td><td className="py-1.5 pr-3">{e.department}</td>
                      <td className="py-1.5 pr-3">{e.complaint}</td><td className="py-1.5 pr-3">{e.provider}</td>
                      <td className="py-1.5">{e.disposition}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {tab === "diagnoses" && (
              <table className="w-full text-sm">
                <thead><tr className="border-b text-left text-muted-foreground">
                  <th className="pb-2 pr-3">ICD-10</th><th className="pb-2 pr-3">Description</th>
                  <th className="pb-2 pr-3">Category</th><th className="pb-2">Chronic</th>
                </tr></thead>
                <tbody>
                  {data.diagnoses.map((d) => (
                    <tr key={d.code} className="border-b"><td className="py-1.5 pr-3 font-mono">{d.code}</td>
                      <td className="py-1.5 pr-3">{d.description}</td><td className="py-1.5 pr-3">{d.category}</td>
                      <td className="py-1.5">{d.isChronic ? <Badge variant="secondary">Chronic</Badge> : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {tab === "medications" && (
              <table className="w-full text-sm">
                <thead><tr className="border-b text-left text-muted-foreground">
                  <th className="pb-2 pr-3">Drug</th><th className="pb-2 pr-3">Dosage</th>
                  <th className="pb-2 pr-3">Frequency</th><th className="pb-2 pr-3">Class</th>
                  <th className="pb-2">Status</th>
                </tr></thead>
                <tbody>
                  {data.medications.map((m) => (
                    <tr key={m.drugName + m.dosage} className="border-b">
                      <td className="py-1.5 pr-3 font-medium">{m.drugName}<br/><span className="text-xs text-muted-foreground">{m.genericName}</span></td>
                      <td className="py-1.5 pr-3">{m.dosage}</td><td className="py-1.5 pr-3">{m.frequency}</td>
                      <td className="py-1.5 pr-3">{m.drugClass}</td>
                      <td className="py-1.5">{m.isActive ? <Badge className="bg-green-600 text-white">Active</Badge> : <Badge variant="secondary">Inactive</Badge>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {tab === "labs" && (
              <table className="w-full text-sm">
                <thead><tr className="border-b text-left text-muted-foreground">
                  <th className="pb-2 pr-3">Test</th><th className="pb-2 pr-3">Value</th>
                  <th className="pb-2 pr-3">Unit</th><th className="pb-2 pr-3">Flag</th>
                  <th className="pb-2">Date</th>
                </tr></thead>
                <tbody>
                  {data.labs.map((l, i) => (
                    <tr key={i} className="border-b"><td className="py-1.5 pr-3">{l.testName}</td>
                      <td className="py-1.5 pr-3 font-mono">{l.value?.toFixed(2)}</td>
                      <td className="py-1.5 pr-3">{l.unit}</td>
                      <td className="py-1.5 pr-3">{l.flag === "Normal" ? l.flag : <Badge className={l.flag === "High" ? "bg-red-600 text-white" : "bg-blue-600 text-white"}>{l.flag}</Badge>}</td>
                      <td className="py-1.5">{l.date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {tab === "claims" && (
              <table className="w-full text-sm">
                <thead><tr className="border-b text-left text-muted-foreground">
                  <th className="pb-2 pr-3">Date</th><th className="pb-2 pr-3">Type</th>
                  <th className="pb-2 pr-3">CPT</th><th className="pb-2 pr-3">Billed</th>
                  <th className="pb-2 pr-3">Paid</th><th className="pb-2">Status</th>
                </tr></thead>
                <tbody>
                  {data.claims.map((c, i) => (
                    <tr key={i} className="border-b"><td className="py-1.5 pr-3">{c.date}</td>
                      <td className="py-1.5 pr-3">{c.type}</td><td className="py-1.5 pr-3 font-mono">{c.cpt}</td>
                      <td className="py-1.5 pr-3 font-mono">${c.billed.toLocaleString()}</td>
                      <td className="py-1.5 pr-3 font-mono">${c.paid.toLocaleString()}</td>
                      <td className="py-1.5"><Badge variant={c.status === "Paid" ? "default" : c.status === "Denied" ? "destructive" : "secondary"}>{c.status}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </CardContent>
      </Card>
    </main>
  )
}

export default function PatientPage() {
  return (
    <Suspense fallback={<p className="p-8 text-muted-foreground">Loading...</p>}>
      <PatientContent />
    </Suspense>
  )
}
