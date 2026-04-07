"""
Hallucination Detector Agent Node
Validates claims against source material
Flags potential hallucinations
"""

import asyncio
from typing import List, Tuple
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from src.models.research import ClaimWithCitation
from src.utils.logger import logger


class HallucinationDetectorNode:
    """
    Detects potential hallucinations in research claims
    Verifies claims against source material
    Returns confidence scores for each claim
    """

    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        self.hallucination_threshold = 0.75
        self.verification_timeout_seconds = 20
        self.max_parallel_verifications = 3

    async def verify_claim(
        self,
        claim: ClaimWithCitation,
        source_content: str
    ) -> Tuple[bool, float]:
        """
        Verify a single claim against source content
        Returns (is_valid, confidence_score)
        """
        prompt = f"""
        Given the following source material and claim, determine if the claim is supported by the source.
        
        Source Material (excerpt):
        {source_content[:1000]}
        
        Claim: {claim.claim}
        
        Respond with:
        1. VALID or UNSUPPORTED
        2. Confidence score (0-1)
        3. Brief explanation
        
        Format as:
        Status: VALID/UNSUPPORTED
        Confidence: 0.85
        Reason: Brief explanation
        """

        try:
            response = await asyncio.wait_for(
                self.llm.ainvoke([HumanMessage(content=prompt)]),
                timeout=self.verification_timeout_seconds,
            )
            response_text = response.content if isinstance(response.content, str) else str(response.content)

            # Parse response
            lines = response_text.split("\n")
            status = "UNSUPPORTED"
            confidence = 0.5

            for line in lines:
                if "Status:" in line:
                    status = "VALID" if "VALID" in line else "UNSUPPORTED"
                elif "Confidence:" in line:
                    try:
                        confidence = float(line.split(":")[-1].strip())
                    except:
                        pass

            is_valid = status == "VALID" and confidence > self.hallucination_threshold
            return is_valid, confidence

        except Exception as e:
            logger.warning(f"Error verifying claim: {e}")
            return False, 0.5

    async def process(
        self,
        claims: List[ClaimWithCitation],
        url_content_map: dict
    ) -> List[str]:
        """
        Verify all claims and return list of hallucination flags
        """
        logger.info(f"Checking {len(claims)} claims for hallucinations")

        semaphore = asyncio.Semaphore(self.max_parallel_verifications)
        hallucination_flags: List[str] = []

        async def _verify_one(claim: ClaimWithCitation) -> str:
            if not claim.citations:
                return f"⚠️ No citation for: {claim.claim}"

            citation = claim.citations[0]
            content = url_content_map.get(citation.url, "")

            if not content:
                return f"⚠️ Could not verify: {claim.claim}"

            async with semaphore:
                is_valid, confidence = await self.verify_claim(claim, content)

            claim.confidence = confidence
            if not is_valid:
                claim.is_hallucination_flagged = True
                return f"🚩 Potential hallucination (confidence {confidence:.0%}): {claim.claim}"

            return ""

        results = await asyncio.gather(*[_verify_one(claim) for claim in claims], return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Claim verification error: {result}")
                continue
            if result:
                hallucination_flags.append(result)

        logger.info(f"Found {len(hallucination_flags)} potential issues")
        return hallucination_flags
