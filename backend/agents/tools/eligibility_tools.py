from langchain_core.tools import tool
from pathlib import Path
import os
import platform
import re
from typing import Optional, List
from pydantic import BaseModel, Field

# Ensure DOCS_DIR points to backend/ so we can locate refund-policy.md
from . import helper
helper.DOCS_DIR = Path(__file__).parent.parent.parent

import contextvars

class EligibilityVerdict(BaseModel):
    is_eligible: bool = Field(description="Whether the customer/item is eligible for a refund according to policy")
    reason: str = Field(description="Detailed reason explaining the decision citing specific policy sections")
    policy_sections: List[str] = Field(description="List of policy sections referenced (e.g., '1. Eligibility for Refunds', '3. Non-Refundable Items')")

_final_verdict: contextvars.ContextVar[Optional[EligibilityVerdict]] = contextvars.ContextVar("_final_verdict", default=None)

@tool
def grep_policy(pattern: str) -> str:
    """
    Search for keyword patterns or terms within the refund-policy.md file.
    Returns lines containing matching terms along with their line numbers.
    Use this to find where specific rules or keywords are located.
    """
    # Try Python first to be robust and cross-platform
    try:
        policy_path = Path(__file__).parent.parent.parent / "refund-policy.md"
        if policy_path.exists():
            with open(policy_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            matches = []
            pattern_lower = pattern.lower()
            for idx, line in enumerate(lines):
                if pattern_lower in line.lower():
                    matches.append(f"Line {idx+1}: {line.strip()}")
            if matches:
                return "\n".join(matches[:15])
    except Exception:
        pass

    # Fallback to helper.grep
    try:
        results = helper.grep(pattern, max_results=10)
        if not results:
            return f"No matches found for pattern '{pattern}' in the policy."
        formatted_results = []
        for r in results:
            parts = r.split(":", 2)
            if len(parts) >= 3:
                line_no = parts[1]
                content = parts[2]
                formatted_results.append(f"Line {line_no}: {content.strip()}")
            else:
                formatted_results.append(r)
        return "\n".join(formatted_results)
    except Exception as e:
        return f"Error executing grep: {str(e)}"

@tool
def read_policy_section(start_line: int, end_line: int) -> str:
    """
    Reads a specific range of lines (start_line to end_line, inclusive, 1-indexed)
    from refund-policy.md. Use this to read the detailed rules of a section
    once you locate it with grep_policy.
    """
    # Try Python first to be robust and cross-platform
    try:
        policy_path = Path(__file__).parent.parent.parent / "refund-policy.md"
        if policy_path.exists():
            with open(policy_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            # 1-indexed, inclusive
            slice_lines = lines[start_line - 1 : end_line]
            return "".join(slice_lines).strip()
    except Exception:
        pass

    # Fallback to helper.read_slice_doc
    try:
        content = helper.read_slice_doc("refund-policy.md", start_line, end_line)
        if not content:
            return f"No content found between lines {start_line} and {end_line}."
        return content
    except Exception as e:
        return f"Error reading policy section: {str(e)}"

@tool
def evaluate_eligibility(is_eligible: bool, reason: str, policy_sections: List[str]) -> str:
    """
    Submit the final eligibility decision for the refund request.
    This tool MUST be called to finish the evaluation. Do NOT try to output
    a text response as the final answer; call this tool instead.
    """
    _final_verdict.set(EligibilityVerdict(
        is_eligible=is_eligible,
        reason=reason,
        policy_sections=policy_sections
    ))
    return "Evaluation submitted successfully. You can stop now."
