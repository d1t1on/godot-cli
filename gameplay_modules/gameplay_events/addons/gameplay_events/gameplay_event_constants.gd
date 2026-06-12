class_name GameplayEventConstants
extends RefCounted

const SAVE_GROUP: StringName = &"save_participants"
const SCHEMA_VERSION: int = 1
const MODULE_VERSION: String = "0.1.0"

const EVENT_EMITTED: String = "event_emitted"
const EVENT_QUEUED: String = "event_queued"
const EVENT_FAILED: String = "event_failed"
const EVENT_QUEUE_FLUSHED: String = "queue_flushed"
const EVENT_QUEUE_CLEARED: String = "queue_cleared"
const EVENT_HISTORY_CLEARED: String = "history_cleared"
const EVENT_STATE_APPLIED: String = "state_applied"
