# AI-Powered Job Scam Detection System

## Overview

An AI-powered system that helps Kenyan job seekers identify potentially fraudulent job postings and assists government reviewers in detecting suspicious recruitment activities.

## Problem Statement

Job scams continue to target Kenyan job seekers through fake local and overseas opportunities. Victims often lose money, personal information, or become exposed to labour trafficking schemes.

## Objectives

- Detect fraudulent job postings.
- Verify employers and recruitment agencies.
- Provide explainable risk assessments.
- Support government review workflows.
- Reduce job scam exposure among job seekers.

## Stakeholders

### Job Seekers

Receive risk assessments and verification results before applying.

### Government Reviewers

Review flagged cases and monitor suspicious entities.

## Proposed Architecture

Job Posting
↓
Content Extraction
↓
NLP Scam Detection
↓
Entity Verification
↓
Risk Assessment
↓
Job Seeker UI / Government Dashboard

## Data Sources

### Real-World Data

- DIFrauD
- BrighterMonday
- Fuzu

### Verification Data

- Mock Company Registry
- Mock Agency Registry

### Testing Data

- Mock Job Postings

## Repository Structure

(brief folder explanation)

## Branching Strategy

main

feature/readme

feature/ui

feature/data-cleaning

feature/eda

feature/modelling

## Commit Convention

feat:
fix:
docs:
data:
test: