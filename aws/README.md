# Workflow

1. Create basic Web Application with `node.js`

2. Manual creation of AWS infrastructure using Management Console. 

- Host application with an EC2 instance
- Edit security group to allow traffic to port 8080 where the application would listen on
- Use SSH connection to download nvm for node and install the application manually

3. Create a CloudFormation Stack for the same infrastructure to automate the process.

- Define a CloudFormation template file `main.yml`
- Understand Infrastructure as code
- Understand CloudFormation template:
  - Parameters
  - Resources: define and configure AWS resources so CloudFormation can manage (SecurityGroup + IAM role + Instance profile + EC2 instance)
  - Outputs: return values for template
- UserData to run commands on EC2 instance when it first launches.

4. Deploy CloudFormation Stack

- `deploy-infra.sh` is used as the script
- Run script to test deployment

5. Automatic Deployments using CodeBuild

- Use GitHub credentials
- Create S3 bucket for build artifacts, it will be created in a separate CloudFormation template called `setup.yml`
- CodeBuild will pull changes from GitHub
- Create simple scripts to tell CodePloy how to start and stop the application
- Define build specification so CodeBuild can build the application in `buildspec.yml`
- Define deployment specification so CodeDeploy what to do with CodeBuild's build artifacts in `appspec.yml`

6. Automatic Deployments by installing CodeDeploy Agent on EC2 so that when a change gets pushed to GitHub, our application is automtically updated

- Add GitHub credentials to `main.yml`
- Add a new policy for EC2 to access CodeDeploy
- Create a new IAM role so that CodeBuild, CodeDeploy and CodePipeline can access AWS resources
- Define CodeBuild project
- Define CodeDeploy application to let it know EC2 is deployment target
- Define a deployment group

7. Create a CodePipeline

- Source stage: Pulls latest code from GitHub
- Build stage: Builds latest code with CodeBuild according to `buildspec.yml`
- Deploy stage: Deploys build artifacts from CodeBuild to EC2 instances referenced in deployment group. Start app according to `appspec.yml`.
- Create a webhook to trigger pipeline as soon as there's a change pushed to GitHub
- Add `ruby` to EC2 instance for CodeDeploy agent. 
- Update `UserData` as CodeDeploy helps download the application from GitHub now

