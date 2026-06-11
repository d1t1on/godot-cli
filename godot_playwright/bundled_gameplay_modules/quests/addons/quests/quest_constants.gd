class_name QuestConstants
extends RefCounted

const SAVE_GROUP: StringName = &"save_participants"
const SCHEMA_VERSION: int = 1
const MODULE_VERSION: String = "0.1.0"

const STATUS_INACTIVE: String = "inactive"
const STATUS_ACTIVE: String = "active"
const STATUS_COMPLETED: String = "completed"
const STATUS_FAILED: String = "failed"

const OBJECTIVE_INACTIVE: String = "inactive"
const OBJECTIVE_ACTIVE: String = "active"
const OBJECTIVE_COMPLETED: String = "completed"

const POLICY_ALL: String = "all"
const POLICY_ANY: String = "any"

const EVENT_QUEST_STARTED: String = "quest_started"
const EVENT_QUEST_COMPLETED: String = "quest_completed"
const EVENT_QUEST_FAILED: String = "quest_failed"
const EVENT_QUEST_STATUS_CHANGED: String = "quest_status_changed"
const EVENT_OBJECTIVE_PROGRESS_CHANGED: String = "objective_progress_changed"
const EVENT_OBJECTIVE_COMPLETED: String = "objective_completed"
const EVENT_QUESTS_CHANGED: String = "quests_changed"
