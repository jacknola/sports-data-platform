"""
Multi-agent system endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from loguru import logger

from app.agents.orchestrator import OrchestratorAgent

router = APIRouter()
orchestrator: "OrchestratorAgent" = None

@router.on_event("startup")
async def startup_event():
    """Initialize the OrchestratorAgent on application startup."""
    global orchestrator
    logger.info("Initializing OrchestratorAgent...")
    orchestrator = await OrchestratorAgent.create()
    logger.info("OrchestratorAgent initialized successfully.")


@router.post("/agents/analyze")
async def run_agent_analysis(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run full agent-based analysis
    
    Args:
        task: Analysis task with sport, teams, date, etc.
        
    Returns:
        Comprehensive analysis from multiple agents
    """
    try:
        result = await orchestrator.execute_full_analysis(task)
        return result
    except Exception as e:
        logger.error(f"Agent analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/learn")
async def submit_learning_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Submit outcome data for agent learning
    
    Args:
        data: Contains analysis_id, actual_outcome, predictions
        
    Returns:
        Learning results
    """
    try:
        await orchestrator.learn_from_outcome(
            data.get('analysis_id'),
            data.get('actual_outcome'),
            data.get('predictions')
        )
        return {"status": "learning_complete"}
    except Exception as e:
        logger.error(f"Learning error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_name}/explain/{decision_id}")
async def explain_agent_decision(agent_name: str, decision_id: str) -> Dict[str, Any]:
    """
    Get detailed explanation of an agent's decision
    
    Args:
        agent_name: Name of the agent
        decision_id: ID of the decision to explain
        
    Returns:
        Detailed explanation
    """
    if agent_name == 'expert':
        # This would retrieve and explain the decision
        return {
            "agent": agent_name,
            "decision_id": decision_id,
            "explanation": "Expert reasoning explanation"
        }
    else:
        return {
            "agent": agent_name,
            "message": "Explanation not available for this agent"
        }


@router.get("/agents/status")
async def get_agents_status() -> Dict[str, Any]:
    """Get status of all agents"""
    try:
        return await orchestrator.get_agent_status()
    except Exception as e:
        logger.error(f"Status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_name}/mistakes")
async def get_agent_mistakes(agent_name: str, limit: int = 10) -> Dict[str, Any]:
    """
    Get mistakes recorded by an agent
    
    Args:
        agent_name: Name of the agent
        limit: Maximum number of mistakes to return
        
    Returns:
        List of mistakes
    """
    # This would retrieve from the agent's mistake history
    return {
        "agent": agent_name,
        "mistakes": [],
        "message": "Mistake retrieval not yet fully implemented"
    }


@router.post("/agents/rag/search")
async def rag_search(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform RAG-powered hybrid search across stored documents.

    Args:
        task: Dict with query (str), optional filters (dict), optional top_k (int).

    Returns:
        Ranked search results with relevance scores.
    """
    if orchestrator is None or orchestrator.rag_agent is None:
        raise HTTPException(status_code=503, detail="RAG agent not initialized")
    try:
        task["type"] = "search"
        result = await orchestrator.rag_agent.execute(task)
        return result
    except Exception as e:
        logger.error(f"RAG search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/rag/store")
async def rag_store(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Store documents in the RAG pipeline for future retrieval.

    Args:
        task: Dict with documents (list of {id, text, metadata}).

    Returns:
        Storage confirmation with count.
    """
    if orchestrator is None or orchestrator.rag_agent is None:
        raise HTTPException(status_code=503, detail="RAG agent not initialized")
    try:
        task["type"] = "chunk_and_store"
        result = await orchestrator.rag_agent.execute(task)
        return result
    except Exception as e:
        logger.error(f"RAG store error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/rag/health")
async def rag_health() -> Dict[str, Any]:
    """Get health status of the RAG subsystem."""
    if orchestrator is None or orchestrator.rag_agent is None:
        return {"status": "unavailable", "vector_store": False, "redis": False}
    return await orchestrator.rag_agent.execute({"type": "health"})

