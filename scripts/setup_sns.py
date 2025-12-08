"""
One-time setup script for SNS topic.
Run this manually in your AWS account.
"""

import os

import boto3
from dotenv import load_dotenv

load_dotenv()

sns = boto3.client(
    "sns",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)


def create_topic():
    """Create SNS topic for task notifications"""
    response = sns.create_topic(
        Name="task-manager-notifications",
        Attributes={"DisplayName": "Task Manager Notifications"},
    )
    topic_arn = response["TopicArn"]
    print(f" Created topic: {topic_arn}")
    print(f"\nAdd this to your .env file:")
    print(f"SNS_TOPIC_ARN={topic_arn}")
    return topic_arn


def test_publish(topic_arn):
    """Send a test notification"""
    response = sns.publish(
        TopicArn=topic_arn,
        Subject="Test Notification",
        Message="If you receive this, SNS is working!",
    )
    print(f" Test message sent: {response['MessageId']}")


if __name__ == "__main__":
    topic_arn = create_topic()
