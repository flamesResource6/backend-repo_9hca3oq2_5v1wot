import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from bson import ObjectId
from datetime import datetime, timezone

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for requests/responses
class SignUpRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class CategoryOut(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None

class ProductOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool
    image_url: Optional[str] = None


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response

# Business endpoints
@app.get("/api/categories", response_model=List[CategoryOut])
def get_categories():
    """Return default categories if database empty; otherwise read from DB"""
    try:
        from database import db, create_document, get_documents
    except Exception:
        # Fallback to static categories if DB not configured
        return [
            {"name": "Engine", "slug": "engine", "description": "Performance engine parts"},
            {"name": "Braking", "slug": "braking", "description": "Pads, rotors, kits"},
            {"name": "Suspension", "slug": "suspension", "description": "Coilovers, arms, bushings"},
            {"name": "Electronics", "slug": "electronics", "description": "Sensors, ECUs, harnesses"},
            {"name": "LED Lighting", "slug": "lighting", "description": "Headlights, strips, kits"},
            {"name": "Bodywork", "slug": "bodywork", "description": "Aero, trims, panels"},
        ]

    # If DB is available, ensure seed exists and return
    existing = list(db["category"].find({}))
    if not existing:
        seed = [
            {"name": "Engine", "slug": "engine", "description": "Performance engine parts", "icon": "Cog"},
            {"name": "Braking", "slug": "braking", "description": "Pads, rotors, kits", "icon": "Disc3"},
            {"name": "Suspension", "slug": "suspension", "description": "Coilovers, arms, bushings", "icon": "Wrench"},
            {"name": "Electronics", "slug": "electronics", "description": "Sensors, ECUs, harnesses", "icon": "Cpu"},
            {"name": "LED Lighting", "slug": "lighting", "description": "Headlights, strips, kits", "icon": "Lightbulb"},
            {"name": "Bodywork", "slug": "bodywork", "description": "Aero, trims, panels", "icon": "Zap"},
        ]
        for s in seed:
            db["category"].insert_one({**s, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)})
        existing = list(db["category"].find({}))

    return [
        {
            "name": c.get("name"),
            "slug": c.get("slug"),
            "description": c.get("description"),
            "icon": c.get("icon"),
        }
        for c in existing
    ]

@app.get("/api/products", response_model=List[ProductOut])
def list_products(category: Optional[str] = None, limit: int = 12):
    try:
        from database import db
    except Exception:
        # Return demo products if DB not configured
        demo = [
            {"_id": "1", "title": "Carbon Intake Kit", "description": "High-flow carbon fiber intake", "price": 299.99, "category": "engine", "in_stock": True, "image_url": None},
            {"_id": "2", "title": "Drilled Brake Rotors", "description": "Performance rotor pair", "price": 189.5, "category": "braking", "in_stock": True, "image_url": None},
        ]
        if category:
            demo = [d for d in demo if d["category"] == category]
        return [
            {
                "id": d.get("_id"),
                "title": d.get("title"),
                "description": d.get("description"),
                "price": d.get("price"),
                "category": d.get("category"),
                "in_stock": d.get("in_stock", True),
                "image_url": d.get("image_url"),
            }
            for d in demo[:limit]
        ]

    q = {}
    if category:
        q["category"] = category
    docs = list(db["product"].find(q).limit(limit))
    return [
        {
            "id": str(d.get("_id")),
            "title": d.get("title"),
            "description": d.get("description"),
            "price": d.get("price"),
            "category": d.get("category"),
            "in_stock": d.get("in_stock", True),
            "image_url": d.get("image_url"),
        }
        for d in docs
    ]

# Simple auth (demo only, not production-ready)
from hashlib import sha256

def hash_password(pw: str) -> str:
    return sha256(pw.encode()).hexdigest()

@app.post("/api/auth/signup")
def signup(payload: SignUpRequest):
    try:
        from database import db
    except Exception:
        # Accept but not persist if DB not configured
        return {"ok": True, "message": "Signed up (demo mode)", "user": {"name": payload.name, "email": payload.email}}

    existing = db["user"].find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    doc = {
        "name": payload.name,
        "email": str(payload.email),
        "password_hash": hash_password(payload.password),
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    res = db["user"].insert_one(doc)
    return {"ok": True, "user_id": str(res.inserted_id)}

@app.post("/api/auth/login")
def login(payload: LoginRequest):
    try:
        from database import db
    except Exception:
        # Demo acceptance
        return {"ok": True, "message": "Logged in (demo mode)", "email": payload.email}

    u = db["user"].find_one({"email": str(payload.email)})
    if not u:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if u.get("password_hash") != hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"ok": True, "user_id": str(u.get("_id")), "name": u.get("name")}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
