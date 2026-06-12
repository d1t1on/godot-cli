class_name GameplayEventBus
extends Node

@export var database: Resource
@export var save_id: StringName
@export var record_history: bool = true
@export_range(0, 10000, 1) var max_history: int = 100
@export var save_history: bool = false
@export var auto_flush: bool = false
@export_range(0, 10000, 1) var auto_flush_limit: int = 0
