# SYSTEM CONTEXT — AGT Booking System

## Purpose
Reusable booking + payment system for service businesses.

## Stack
Frontend: GitHub Pages (vanilla JS)
Backend: AWS Lambda + API Gateway
Database: DynamoDB
Payments: Stripe Checkout
Scheduling: Cal.com API
SMS: Textbelt
Infra: Terraform

## Core Rules
- DynamoDB = source of truth
- Stripe = payments only
- Cal.com = scheduling only
- No business logic in frontend
- All pricing validated in backend

## Booking Flow
1. Frontend builds booking
2. Backend creates booking record
3. User selects time
4. Stripe checkout created
5. Payment completed
6. Webhook confirms booking
7. SMS sent

## Code Standards
- No duplicate logic
- No unused code
- No hardcoded secrets
- Validate all inputs
- Keep functions small

## Cost Constraint
< $10/month per client

## AI Rules
- Do not overengineer
- Do not introduce new services
- Prefer simple solutions
