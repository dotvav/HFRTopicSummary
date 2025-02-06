# HFRTopicSummary

If you are looking for the userscript, look here: https://github.com/dotvav/hfr-stuff. That is the client part of that project.

## What's that?

This is a stack that hosts the backend of a topic summarizer for HFR. It includes:
 
* 3 DynamoDB tables: topics (not used at the moment), messages, summaries.
* A lambda function (request handler), linked to an API, that takes user requests and responds with the summary status and content. Writes the request in the DynamoDB summaries table if it doesn't exist.
* A lambda function (stream processor) that is subscribed to the summaries table events and pushes a message in a SQS queue when a summary status is created or updated.
* A lambda function (summary generator) that processes requests from SQS, reads the messages from the messages table, loads messages from HFR if needed, prepares the summary with Claude on Bedrock, and finally updates the status.

The stack comes with 2 environments: "devo" and "prod".

## Developer cheat sheet

### SAM CLI
You will need the SAM CLI to be installed and configured for your AWS account.

More info here: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html

Plenty of tutorials on the internet.

### Development life cycle

The project comes with a few VisualStudioCode tasks, in order to help with the flow:

* Local Invoke: Summary Generator: runs the summary generator locally on your workstation. Requires docker running. Uses èvents/summary_generator/sqs_event.json`, which you can modify with the topic id and date of your choice.
* Deploy to AWS: well, deploys the stack to AWS.

These tasks will ask which environment to use. I suggest you use "devo" for testing, and and only deploy to "prod" when your tests are successful. 

I haven't found a clean reliable way to attach a debugger to a local invocation, so I resort to a lot of DEBUG logging.
