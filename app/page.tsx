"use client"

import { useEffect, useState, useCallback } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import Link from "next/link"

interface Patient {
  patientId: string
  firstName: string
  lastName: string
  dob: string
  gender: string
  insuranceType: string
  insurancePayer: string
  pcpName: string
  state: string
  riskTier: string | null
  hccScore: number | null
  readmissionRisk: number | null
  medAdherence: number | null
  riskFactors: string | null
}

const riskColors: Record<string, string> = {
  Critical: "bg-red-600 text-white",
  High: "bg-orange-500 text-white",
  Moderate: "bg-yellow-500 text-black",
  Low: "bg-green-600 text-white",
}

export default function HomePage() {
  const [patients, setPatients] = useState<Patient[]>([])
  const [search, setSearch] = useState("")
  const [loading, setLoading] = useState(true)
  const [filterTier, setFilterTier] = useState<string | null>(null)

  const loadPatients = useCallback(async (query: string) => {
    setLoading(true)
    try {
      const res = await fetch(`/api/patients?search=${encodeURIComponent(query)}`)
      if (res.ok) setPatients(await res.json())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadPatients("")
  }, [loadPatients])

  const filtered = filterTier
    ? patients.filter((p) => p.riskTier === filterTier)
    : patients

  const tiers = ["Critical", "High", "Moderate", "Low"]
  const tierCounts = tiers.reduce((acc, t) => {
    acc[t] = patients.filter((p) => p.riskTier === t).length
    return acc
  }, {} as Record<string, number>)

  return (
    <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Patient 360 Copilot</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Unified EHR, claims, and clinical document intelligence
          </p>
        </div>
        <Link href="/copilot">
          <Button>Open Copilot Chat</Button>
        </Link>
      </div>

      {/* Risk tier summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {tiers.map((tier) => (
          <Card
            key={tier}
            className={`cursor-pointer transition-all ${filterTier === tier ? "ring-2 ring-primary" : ""}`}
            onClick={() => setFilterTier(filterTier === tier ? null : tier)}
          >
            <CardContent className="pt-4 pb-4 flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">
                  {tier} Risk
                </p>
                <p className="text-2xl font-bold">{tierCounts[tier]}</p>
              </div>
              <Badge className={riskColors[tier]}>{tier}</Badge>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Search */}
      <div className="flex gap-3">
        <input
          type="text"
          placeholder="Search by name or patient ID..."
          className="flex-1 px-3 py-2 border rounded-md bg-background text-foreground"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && loadPatients(search)}
        />
        <Button variant="secondary" onClick={() => loadPatients(search)}>
          Search
        </Button>
        {filterTier && (
          <Button variant="outline" onClick={() => setFilterTier(null)}>
            Clear Filter
          </Button>
        )}
      </div>

      {/* Patient table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            {filterTier ? `${filterTier} Risk Patients` : "All Patients"} ({filtered.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground text-center py-8">Loading patients...</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="pb-2 pr-4">Patient</th>
                    <th className="pb-2 pr-4">ID</th>
                    <th className="pb-2 pr-4">Gender</th>
                    <th className="pb-2 pr-4">Insurance</th>
                    <th className="pb-2 pr-4">PCP</th>
                    <th className="pb-2 pr-4">Risk Tier</th>
                    <th className="pb-2 pr-4">HCC Score</th>
                    <th className="pb-2 pr-4">Readmission %</th>
                    <th className="pb-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((p) => (
                    <tr key={p.patientId} className="border-b hover:bg-muted/50">
                      <td className="py-2 pr-4 font-medium">{p.firstName} {p.lastName}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{p.patientId}</td>
                      <td className="py-2 pr-4">{p.gender}</td>
                      <td className="py-2 pr-4">{p.insuranceType}</td>
                      <td className="py-2 pr-4">{p.pcpName}</td>
                      <td className="py-2 pr-4">
                        {p.riskTier && (
                          <Badge className={riskColors[p.riskTier] || ""}>{p.riskTier}</Badge>
                        )}
                      </td>
                      <td className="py-2 pr-4 font-mono">{p.hccScore?.toFixed(2) ?? "-"}</td>
                      <td className="py-2 pr-4 font-mono">{p.readmissionRisk?.toFixed(0) ?? "-"}%</td>
                      <td className="py-2">
                        <div className="flex gap-2">
                          <Link href={`/patient?id=${p.patientId}`}>
                            <Button variant="outline" size="sm">View 360</Button>
                          </Link>
                          <Link href={`/copilot?patient=${p.patientId}`}>
                            <Button variant="outline" size="sm">Ask Copilot</Button>
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
