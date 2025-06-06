from fastapi import APIRouter, Depends, HTTPException, Query
import os
from pathlib import Path


router = APIRouter()


@router.get("/legal")
def privacy_terms(
    document: str = Query(..., description="Legal document to retrieve")
) -> dict:
    """
    Get legal documents like privacy policy and terms of service.
    """
    # Define allowed documents to prevent path traversal
    allowed_documents = {"privacy_policy", "terms_of_service", "cookie_policy"}

    if document not in allowed_documents:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document type. Allowed types: {', '.join(allowed_documents)}",
        )

    try:
        # Get the base directory and construct the proper path
        base_dir = (
            Path(__file__).resolve().parents[4]
        )  # Go up to the primary_api directory
        file_path = base_dir / "app" / "assets" / "legal" / f"{document}.md"

        if not file_path.exists():
            raise FileNotFoundError(f"Document file not found: {file_path}")

        with open(file_path, "r") as file:
            content = file.read()

        return {
            "content": content,
            "privacy_policy_url": "https://www.example.com/privacy-policy",
            "terms_of_service_url": "https://www.example.com/terms-of-service",
        }
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404, detail=f"Legal document '{document}' not found: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error reading legal document: {str(e)}"
        )
