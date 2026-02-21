# Agent System

## Overview
A multi-agent orchestration system that automates sports betting intelligence through specialized roles and feedback loops.

## Agents
| Agent | Class | Responsibility |
|-------|-------|----------------|
| BaseAgent | BaseAgent | Abstract base with execute(), learn_from_mistake() |
| OrchestratorAgent | OrchestratorAgent | Coordinates all agents |
| OddsAgent | OddsAgent | Fetch odds, identify value bets |
| AnalysisAgent | AnalysisAgent | Bayesian/ML analysis |
| ScrapingAgent | ScrapingAgent | Web scraping |
| TwitterAgent | TwitterAgent | Sentiment analysis |
| ExpertAgent | ExpertAgent | Sequential thinking |

## Orchestration
The system follows a pipeline pattern managed by the OrchestratorAgent. It starts by fetching market odds to find value. Then, it gathers context through web scraping and social sentiment. Finally, it runs Bayesian models and expert reasoning to reach a betting decision.

## Communication
Agents communicate through structured dictionaries passed by the orchestrator. Each agent receives a task object and returns a result object. This decoupled approach lets the orchestrator manage the flow and handle errors at each step.

## Local Conventions
Agents inherit from BaseAgent to ensure consistent execution and error handling. They use a self-correction mechanism where they record mistakes and adjust parameters for future tasks. This learning process helps the system improve its accuracy over time. Every new agent must follow this pattern to maintain system integrity.
