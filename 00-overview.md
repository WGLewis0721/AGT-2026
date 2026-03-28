# TRA3 Master Rebuild — Prompt Breakdown
# Split between VS Code Copilot (AWS access) and GitHub.com Copilot (code only)
# Run in this exact order

---

## PROMPT 1 — GitHub.com Copilot
### "Write Terraform files"
Scope: Write all .tf files only. No AWS calls. No deploys.
File: prompts/01-terraform-files.md

## PROMPT 2 — GitHub.com Copilot
### "Write Lambda function"
Scope: Write lambda_function.py and requirements files only.
File: prompts/02-lambda-function.md

## PROMPT 3 — GitHub.com Copilot
### "Write deploy scripts"
Scope: Write deploy.ps1 and bootstrap-layer.ps1 only.
File: prompts/03-deploy-scripts.md

## PROMPT 4 — GitHub.com Copilot
### "Write client tfvars and gitignore"
Scope: Write tfvars files, update .gitignore only.
File: prompts/04-config-files.md

## PROMPT 5 — VS Code Copilot (AWS)
### "Destroy existing infrastructure"
Scope: Run terraform destroy on rosie-* resources. Requires AWS creds.
File: prompts/05-destroy.md

## PROMPT 6 — VS Code Copilot (AWS)
### "Bootstrap layer and deploy"
Scope: Run bootstrap-layer.ps1, deploy dev, deploy prod. Requires AWS creds.
File: prompts/06-deploy.md

## PROMPT 7 — GitHub.com Copilot
### "Write documentation"
Scope: Write README and Copilot instructions. No AWS. No deploy.
File: prompts/07-docs.md

---

Run order:
  1 → 2 → 3 → 4 (GitHub.com, any order within this group)
  5 → 6          (VS Code, must be in order)
  7              (GitHub.com, after deploy confirms working)
