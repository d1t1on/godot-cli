extends PanelContainer

@onready var state_label: Label = $VBox/StateLabel
@onready var detail_label: Label = $VBox/DetailLabel


func _ready() -> void:
	set_status("Booting", {})


func set_status(state: String, details: Dictionary) -> void:
	state_label.text = state
	detail_label.text = JSON.stringify(details)
	set_meta("state", state)
	set_meta("details", details)
