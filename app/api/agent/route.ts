import { querySnowflake } from "@/lib/snowflake"
import { AGENT_NAME } from "@/lib/constants"

export const dynamic = "force-dynamic"

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const { messages, patientId } = body as {
      messages: { role: string; text: string }[]
      patientId?: string
    }

    if (!messages?.length) {
      return Response.json({ error: "No messages provided" }, { status: 400 })
    }

    const lastMessage = messages[messages.length - 1]
    let userText = lastMessage.text

    if (patientId) {
      userText = `[Context: Patient ID is ${patientId}] ${userText}`
    }

    const agentMessages = messages.map((m) => ({
      role: m.role,
      content: [{ type: "text", text: m.role === "user" && m === lastMessage ? userText : m.text }],
    }))

    const sql = `SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
      '${AGENT_NAME}',
      ?,
      TRUE
    ) AS response`

    const payload = JSON.stringify({ messages: agentMessages })
    const rows = await querySnowflake(sql, { binds: [payload] })
    const row = (rows as Record<string, unknown>[])[0]

    if (!row?.RESPONSE) {
      return Response.json({ error: "No response from agent" }, { status: 500 })
    }

    let parsed: Record<string, unknown>
    try {
      parsed = typeof row.RESPONSE === "string" ? JSON.parse(row.RESPONSE) : (row.RESPONSE as Record<string, unknown>)
    } catch {
      return Response.json({ text: String(row.RESPONSE), citations: [] })
    }

    const content = parsed.content as Array<Record<string, unknown>> | undefined
    if (!content) {
      return Response.json({ text: JSON.stringify(parsed), citations: [] })
    }

    let text = ""
    const citations: Array<Record<string, unknown>> = []
    const tables: Array<Record<string, unknown>> = []

    for (const item of content) {
      if (item.type === "text") {
        text += String(item.text || "")
        const annotations = item.annotations as Array<Record<string, unknown>> | undefined
        if (annotations) {
          for (const ann of annotations) {
            citations.push({
              type: String(ann.type || ""),
              title: String(ann.doc_title || ""),
              text: String(ann.text || ""),
              index: ann.index,
            })
          }
        }
      } else if (item.type === "tool_result") {
        const toolResult = item.tool_result as Record<string, unknown> | undefined
        if (toolResult) {
          const resultContent = toolResult.content as Array<Record<string, unknown>> | undefined
          if (resultContent) {
            for (const rc of resultContent) {
              if (rc.type === "json") {
                const json = rc.json as Record<string, unknown>
                if (json?.result_set) {
                  tables.push(json.result_set as Record<string, unknown>)
                }
              }
            }
          }
        }
      }
    }

    return Response.json({ text, citations, tables })
  } catch (e) {
    console.error(new Date().toISOString(), "[agent]", e)
    return Response.json(
      { error: e instanceof Error ? e.message : "Agent request failed" },
      { status: 500 }
    )
  }
}
