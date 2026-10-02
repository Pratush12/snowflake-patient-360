"use client"

import { useState, useRef, useEffect, Suspense } from "react"
import { useSearchParams } from "next/navigation"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import Link from "next/link"

interface Citation {
  type: string
  title: string
  text: string
  index: number
}

interface Message {
  role: "user" | "assistant"
  text: string
  citations?: Citation[]
  loading?: boolean
}

const sampleQuestions = [
  "Which patients have the highest risk of readmission?",
  "What are the FDA safety alerts about metformin?",
  "Show me all patients with Critical risk tier",
  "What do the clinical guidelines say about heart failure management?",
  "Which patients have the most denied insurance claims?",
  "What are the common drug interactions with statins?",
]

function CopilotContent() {
  const searchParams = useSearchParams()
  const patientParam = searchParams.get("patient")
  const [patientId, setPatientId] = useState(patientParam || "")
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const sendMessage = async (text: string) => {
    if (!text.trim() || sending) return
    const userMsg: Message = { role: "user", text }
    const loadingMsg: Message = { role: "assistant", text: "", loading: true }
    setMessages((prev) => [...prev, userMsg, loadingMsg])
    setInput("")
    setSending(true)

    try {
      const history = [...messages, userMsg].map((m) => ({
        role: m.role,
        text: m.text,
      }))

      const res = await fetch("/api/agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: history,
          patientId: patientId || undefined,
        }),
      })

      const data = await res.json()

      if (data.error) {
        setMessages((prev) => [
          ...prev.slice(0, -1),
          { role: "assistant", text: `Error: ${data.error}` },
        ])
      } else {
        setMessages((prev) => [
          ...prev.slice(0, -1),
          {
            role: "assistant",
            text: data.text || "No response from agent.",
            citations: data.citations || [],
          },
        ])
      }
    } catch (e) {
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { role: "assistant", text: `Error: ${e instanceof Error ? e.message : "Request failed"}` },
      ])
    } finally {
      setSending(false)
    }
  }

  return (
    <main className="max-w-5xl mx-auto px-4 py-6 flex flex-col h-[calc(100vh-64px)]">
      <div className="flex items-center gap-4 mb-4">
        <Link href="/"><Button variant="outline" size="sm">Back</Button></Link>
        <h1 className="text-xl font-semibold">Healthcare Copilot</h1>
        <div className="ml-auto flex items-center gap-2">
          <label className="text-sm text-muted-foreground">Patient scope:</label>
          <input
            type="text"
            placeholder="e.g. P-0001 (optional)"
            className="px-2 py-1 border rounded text-sm bg-background w-32"
            value={patientId}
            onChange={(e) => setPatientId(e.target.value)}
          />
          {patientId && (
            <Button variant="ghost" size="sm" onClick={() => setPatientId("")}>Clear</Button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.length === 0 && (
          <div className="text-center py-12 space-y-6">
            <div>
              <h2 className="text-lg font-medium">Ask me about patients, clinical data, or regulatory guidelines</h2>
              <p className="text-muted-foreground text-sm mt-1">
                I combine structured EHR/claims data with clinical documents to provide cited answers.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 max-w-2xl mx-auto">
              {sampleQuestions.map((q) => (
                <button
                  key={q}
                  className="text-sm px-3 py-2 border rounded-lg hover:bg-muted transition-colors text-left"
                  onClick={() => sendMessage(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-3 ${
                msg.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-card border"
              }`}
            >
              {msg.loading ? (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <div className="animate-pulse">Thinking...</div>
                </div>
              ) : (
                <>
                  <div className="whitespace-pre-wrap text-sm">{msg.text}</div>
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-3 space-y-2">
                      <p className="text-xs font-medium text-muted-foreground">Sources:</p>
                      {msg.citations.map((c, ci) => (
                        <Card key={ci} className="bg-muted/50">
                          <CardContent className="py-2 px-3">
                            <div className="flex items-center gap-2 mb-1">
                              <Badge variant="secondary" className="text-[10px]">
                                {c.type === "cortex_search_citation" ? "Document" : "Source"}
                              </Badge>
                              <span className="text-xs font-medium">{c.title}</span>
                            </div>
                            <p className="text-xs text-muted-foreground line-clamp-3">{c.text}</p>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex gap-2 pt-4 border-t">
        <input
          type="text"
          placeholder={patientId ? `Ask about patient ${patientId}...` : "Ask a clinical or regulatory question..."}
          className="flex-1 px-3 py-2 border rounded-md bg-background text-foreground"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage(input)}
          disabled={sending}
        />
        <Button onClick={() => sendMessage(input)} disabled={sending || !input.trim()}>
          Send
        </Button>
      </div>
    </main>
  )
}

export default function CopilotPage() {
  return (
    <Suspense fallback={<p className="p-8 text-muted-foreground">Loading...</p>}>
      <CopilotContent />
    </Suspense>
  )
}
