/** App title — displayed in the nav header and browser tab */
export const APP_TITLE = "Patient 360 Copilot"

/** Path to the logo in /public (used in the header and as favicon) */
export const LOGO_SRC = "/icon.svg"

/** Snowflake database/schema for all healthcare data */
export const HC_DB = "HEALTHCARE_COPILOT"
export const HC_SCHEMA = "CORE"

/** Cortex Agent fully-qualified name */
export const AGENT_NAME = `${HC_DB}.${HC_SCHEMA}.PATIENT_COPILOT`
