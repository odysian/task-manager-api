resource "aws_sns_topic" "notifications" {
  name         = "${var.project_name}-notifications"
  display_name = "Task Manager"
}