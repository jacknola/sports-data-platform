"""
Parlay ingestion service: fetch user tweets, parse parlays, persist to DB, and index via RAG.
"""
from __future__ import annotations

from typing import List, Dict, Any
from datetime import datetime
from loguru import logger

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.twitter_analyzer import TwitterAnalyzer
from app.services.rag_service import RAGService, RAGDocument
from app.models.parlay import Parlay, ParlayLeg


class ParlayIngestionService:
    def __init__(self):
        self._twitter = TwitterAnalyzer()
        self._rag = RAGService()
        self._initialized = False

    async def _ensure_init(self):
        if not self._initialized:
            await self._rag.init()
            self._initialized = True

    async def ingest_user_parlays(self, username: str, max_results: int = 20) -> Dict[str, Any]:
        """Fetch user's tweets, parse parlays, save, and embed."""
        await self._ensure_init()
        tweets = self._twitter.fetch_user_parlay_tweets(username, max_results=max_results)
        if not tweets:
            return {"username": username, "ingested": 0, "parlays": []}

        db: Session = SessionLocal()
        created: List[int] = []
        parlays_meta: List[Dict[str, Any]] = []
        rag_docs: List[RAGDocument] = []

        try:
            for t in tweets:
                parsed = self._twitter.parse_parlay_from_text(t["text"]) or {}
                legs = parsed.get("legs", [])
                if not legs:
                    continue

                # Check duplicate by tweet id
                existing = (
                    db.query(Parlay).filter(Parlay.source == "twitter", Parlay.tweet_id == str(t["id"]))
                    .first()
                )
                if existing:
                    logger.info(f"Parlay already exists for tweet {t['id']}")
                    continue

                parlay = Parlay(
                    source="twitter",
                    tweet_id=str(t["id"]),
                    author_username=t.get("author_username"),
                    author_user_id=str(t.get("author_id")) if t.get("author_id") else None,
                    posted_at=datetime.fromisoformat(t["created_at"]) if t.get("created_at") else None,
                    title=parsed.get("title"),
                    description=t["text"],
                    num_legs=parsed.get("num_legs"),
                    total_odds_american=parsed.get("total_odds_american"),
                    stake_units=parsed.get("stake_units"),
                    metadata={"public_metrics": t.get("public_metrics")},
                )
                db.add(parlay)
                db.flush()  # get parlay.id

                for leg_idx, leg in enumerate(legs):
                    leg_rec = ParlayLeg(
                        parlay_id=parlay.id,
                        order_index=leg.get("order_index", leg_idx),
                        sport=None,
                        league=None,
                        game_id=None,
                        team=leg.get("team"),
                        player=leg.get("player"),
                        market=leg.get("market"),
                        selection=leg.get("selection"),
                        line=leg.get("line"),
                        odds_american=None,
                    )
                    db.add(leg_rec)

                db.commit()
                created.append(parlay.id)

                # Prepare RAG doc
                doc_id = f"parlay:{parlay.id}"
                rag_docs.append(
                    RAGDocument(
                        doc_id=doc_id,
                        text=t["text"],
                        metadata={
                            "type": "parlay",
                            "parlay_id": parlay.id,
                            "author_username": parlay.author_username,
                            "num_legs": parlay.num_legs,
                            "total_odds_american": parlay.total_odds_american,
                        },
                    )
                )
                parlays_meta.append(
                    {
                        "parlay_id": parlay.id,
                        "tweet_id": t["id"],
                        "author": parlay.author_username,
                        "num_legs": parlay.num_legs,
                        "total_odds_american": parlay.total_odds_american,
                    }
                )

            if rag_docs:
                await self._rag.upsert(rag_docs)
                await self._rag.add_to_index([d.doc_id for d in rag_docs])

            return {"username": username, "ingested": len(created), "parlays": parlays_meta}
        except Exception as e:
            db.rollback()
            logger.error(f"Parlay ingestion error: {e}")
            raise
        finally:
            db.close()
