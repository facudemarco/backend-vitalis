from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from auth.authentication import require_roles, require_active_user
from models.user import UserSchema
from Database.getConnection import getConnectionForLogin
from sqlalchemy import text
import uuid
from typing import List, Optional

router = APIRouter(prefix="/support", tags=["Support"])

# ==================== PYDANTIC SCHEMAS ====================

class TicketCreate(BaseModel):
    subject: str
    body: str

class TicketResponse(BaseModel):
    response: str

# ==================== HELPERS ====================

def _format_ticket(row) -> dict:
    """Formats ticket database row to dict"""
    return {
        "id": row["id"],
        "subject": row["subject"],
        "body": row["body"],
        "status": row["status"],
        "user_id": row["user_id"],
        "user_role": row["user_role"],
        "response": row["response"],
        "created_at": str(row["created_at"]) if row["created_at"] else None,
        "updated_at": str(row["updated_at"]) if row["updated_at"] else None,
    }

# ==================== ENDPOINTS ====================

@router.post("/tickets", response_model=dict)
async def create_ticket(
    ticket_data: TicketCreate,
    current_user: UserSchema = Depends(require_active_user)
):
    """Create a new support ticket"""
    if current_user.role not in ("company", "patient"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only companies or patients can create support tickets."
        )
        
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
        
    ticket_id = str(uuid.uuid4())
    try:
        db.execute(text("""
            INSERT INTO support_tickets (id, subject, body, status, user_id, user_role, response)
            VALUES (:id, :subject, :body, 'pending', :user_id, :user_role, NULL)
        """), {
            "id": ticket_id,
            "subject": ticket_data.subject,
            "body": ticket_data.body,
            "user_id": current_user.id,
            "user_role": current_user.role
        })
        db.commit()
        
        # Fetch the created ticket to return it
        row = db.execute(text("""
            SELECT id, subject, body, status, user_id, user_role, response, created_at, updated_at
            FROM support_tickets
            WHERE id = :id
        """), {"id": ticket_id}).mappings().first()
        
        if not row:
            raise HTTPException(status_code=500, detail="Failed to retrieve created ticket")
            
        return _format_ticket(row)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error creating ticket: " + str(e))
    finally:
        db.close()

@router.get("/tickets", response_model=dict)
async def get_all_tickets(
    current_user: UserSchema = Depends(require_roles("admin"))
):
    """List all tickets for admin"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
        
    try:
        rows = db.execute(text("""
            SELECT id, subject, body, status, user_id, user_role, response, created_at, updated_at
            FROM support_tickets
            ORDER BY created_at DESC
        """)).mappings().all()
        
        tickets = [_format_ticket(row) for row in rows]
        return {"tickets": tickets, "total": len(tickets)}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching tickets: " + str(e))
    finally:
        db.close()

@router.get("/my-tickets", response_model=dict)
async def get_my_tickets(
    current_user: UserSchema = Depends(require_active_user)
):
    """List tickets for the current company or patient"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
        
    try:
        rows = db.execute(text("""
            SELECT id, subject, body, status, user_id, user_role, response, created_at, updated_at
            FROM support_tickets
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """), {"user_id": current_user.id}).mappings().all()
        
        tickets = [_format_ticket(row) for row in rows]
        return {"tickets": tickets, "total": len(tickets)}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching user tickets: " + str(e))
    finally:
        db.close()

@router.get("/tickets/{ticket_id}", response_model=dict)
async def get_ticket_by_id(
    ticket_id: str,
    current_user: UserSchema = Depends(require_active_user)
):
    """Get detail of a ticket by id"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
        
    try:
        row = db.execute(text("""
            SELECT id, subject, body, status, user_id, user_role, response, created_at, updated_at
            FROM support_tickets
            WHERE id = :id
        """), {"id": ticket_id}).mappings().first()
        
        if not row:
            raise HTTPException(status_code=404, detail="Ticket not found")
            
        # Security: admin can see all, company/patient only their own
        if current_user.role != "admin" and row["user_id"] != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this ticket."
            )
            
        return _format_ticket(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching ticket detail: " + str(e))
    finally:
        db.close()

@router.patch("/tickets/{ticket_id}", response_model=dict)
async def respond_ticket(
    ticket_id: str,
    payload: TicketResponse,
    current_user: UserSchema = Depends(require_roles("admin"))
):
    """Respond to a support ticket (admin only)"""
    db = getConnectionForLogin()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection error")
        
    try:
        # Check if ticket exists
        row = db.execute(text("""
            SELECT id FROM support_tickets WHERE id = :id
        """), {"id": ticket_id}).mappings().first()
        
        if not row:
            raise HTTPException(status_code=404, detail="Ticket not found")
            
        # Update response and status to 'answered'
        db.execute(text("""
            UPDATE support_tickets
            SET response = :response, status = 'answered'
            WHERE id = :id
        """), {
            "id": ticket_id,
            "response": payload.response
        })
        db.commit()
        
        # Return updated ticket
        updated_row = db.execute(text("""
            SELECT id, subject, body, status, user_id, user_role, response, created_at, updated_at
            FROM support_tickets
            WHERE id = :id
        """), {"id": ticket_id}).mappings().first()
        
        return _format_ticket(updated_row)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error responding to ticket: " + str(e))
    finally:
        db.close()
