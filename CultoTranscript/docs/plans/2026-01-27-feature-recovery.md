# CultoTranscript Feature Recovery Plan

> **For Claude:** Use parallel Task agents to implement and validate. Execute by priority group. Don't report complete until ALL features verified via browser.

**Goal:** Restore ALL missing/broken features after React migration

**Tech Stack:** React, TypeScript, Tailwind CSS v4, FastAPI, PostgreSQL

---

## COMPLETE LOST FEATURES ANALYSIS

### From Old Jinja Templates vs New React Components

| # | Feature | Old Location | Status in React | Priority |
|---|---------|--------------|-----------------|----------|
| 1 | **Video Import (Single)** | admin_import.html | REMOVED | Critical |
| 2 | **Video Import (Bulk with filters)** | admin_import.html | REMOVED | Critical |
| 3 | **6-Step Progress Tracker** | admin_import.html | REMOVED | Critical |
| 4 | **Members list + management** | admin.html | Stub only (no data) | Critical |
| 5 | **Invite member button** | admin.html | No handler | Critical |
| 6 | **Knowledge mode toggle** | chatbot.html | REMOVED | Critical |
| 7 | **API Key Config UI** | admin.html | REMOVED | Critical |
| 8 | **Token Usage Display** | admin.html | REMOVED | High |
| 9 | **Video Duration Config** | admin.html | REMOVED | High |
| 10 | **Drawer resize** | index.html | REMOVED | High |
| 11 | **Push-left drawer behavior** | index.html | REMOVED | High |
| 12 | **Settings page (password)** | - | Stub only | High |
| 13 | **Profile menu expansion** | - | Only logout | High |
| 14 | **Scheduler status widget** | admin_schedule.html | REMOVED | Medium |
| 15 | **Channel header banner** | admin.html | REMOVED | Medium |
| 16 | **Tab navigation in Admin** | admin.html | REMOVED | Medium |
| 17 | **Chatbot metrics page** | admin_chatbot_metrics.html | REMOVED | Medium |
| 18 | **WebSub management page** | admin_websub.html | REMOVED | Low |
| 19 | **Channels list page** | channels/list.html | REMOVED | Low |
| 20 | **Database table browser** | database.html | Degraded | Low |
| 21 | **Contrast fixes** | - | Poor dark mode | Medium |
| 22 | **Routing cleanup** | - | /channels redundant | Low |

---

## PHASE 1: CRITICAL (Backend First)

### Task 1.1: Members Backend Endpoints

**File:** `app/web/routes/api.py` (add after line 1764)

```python
# ============================================================================
# Church Members Endpoints
# ============================================================================

@router.get("/church/members")
async def get_church_members(
    channel_id: Optional[int] = None,
    request: Request = None,
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """Get members for a church channel"""
    from app.common.models import ChurchMember, User

    cid = channel_id or request.session.get("channel_id", 1)

    members = db.query(
        ChurchMember.id,
        ChurchMember.role,
        User.email,
        User.last_login,
        User.login_count
    ).join(User, ChurchMember.user_id == User.id).filter(
        ChurchMember.channel_id == cid
    ).all()

    return {
        "members": [
            {
                "id": m.id,
                "email": m.email,
                "role": m.role,
                "last_login": m.last_login.isoformat() if m.last_login else None,
                "login_count": m.login_count
            }
            for m in members
        ]
    }

@router.post("/church/members/invite")
async def invite_member(
    request: Request,
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """Invite a new member to the church"""
    from app.common.models import ChurchMember, User

    data = await request.json()
    email = data.get("email")
    role = data.get("role", "user")
    channel_id = data.get("channel_id") or request.session.get("channel_id", 1)

    if role not in ("owner", "admin", "user"):
        return {"success": False, "message": "Invalid role"}

    existing_user = db.query(User).filter(User.email == email).first()

    if existing_user:
        existing_membership = db.query(ChurchMember).filter(
            ChurchMember.user_id == existing_user.id,
            ChurchMember.channel_id == channel_id
        ).first()

        if existing_membership:
            return {"success": False, "message": "User is already a member"}

        membership = ChurchMember(
            user_id=existing_user.id,
            channel_id=channel_id,
            role=role,
            invited_by=request.session.get("user_id")
        )
        db.add(membership)
        db.commit()

        return {"success": True, "message": "Member added successfully"}
    else:
        return {"success": False, "message": "User not found. They must register first."}

@router.delete("/church/members/{member_id}")
async def remove_member(
    member_id: int,
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """Remove a member from the church"""
    from app.common.models import ChurchMember

    membership = db.query(ChurchMember).filter(ChurchMember.id == member_id).first()
    if not membership:
        return {"success": False, "message": "Member not found"}

    db.delete(membership)
    db.commit()
    return {"success": True, "message": "Member removed"}
```

**Add to CSRF exempt paths in `app/web/main.py`:**
```python
"/api/church/members",
```

---

### Task 1.2: User Profile/Password Endpoints

**File:** `app/web/routes/api.py`

```python
@router.get("/user/profile")
async def get_user_profile(
    request: Request,
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    from app.common.models import User
    user_id = request.session.get("user_id")
    user_obj = db.query(User).filter(User.id == user_id).first()
    if not user_obj:
        return {"success": False, "message": "User not found"}
    return {
        "success": True,
        "data": {
            "email": user_obj.email,
            "created_at": user_obj.created_at.isoformat() if user_obj.created_at else None
        }
    }

@router.post("/user/change-password")
async def change_password(
    request: Request,
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    from app.common.models import User
    import bcrypt

    data = await request.json()
    current_password = data.get("current_password")
    new_password = data.get("new_password")

    user_id = request.session.get("user_id")
    user_obj = db.query(User).filter(User.id == user_id).first()

    if not bcrypt.checkpw(current_password.encode(), user_obj.password_hash.encode()):
        return {"success": False, "message": "Senha atual incorreta"}

    new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    user_obj.password_hash = new_hash
    db.commit()

    return {"success": True, "message": "Senha alterada"}
```

---

### Task 1.3: Knowledge Mode Backend Wiring

**File:** `Backend/dtos.py` (line 176-180)
```python
class ChatRequestDTO(BaseModel):
    """Chat request"""
    message: str
    session_id: str
    channel_id: str
    knowledge_mode: Optional[str] = "database_only"  # ADD
```

**File:** `Backend/api/v2/chat.py` (line 83-87)
```python
response_data = chatbot_service.chat(
    channel_id=int(channel_id),
    user_message=request.message,
    session_id=request.session_id,
    knowledge_mode=request.knowledge_mode  # ADD
)
```

---

## PHASE 2: CRITICAL (Frontend)

### Task 2.1: Admin Page - Tab Navigation & Import

**File:** `UI/src/pages/Admin.tsx`

Restructure with tabs:
1. **Import Tab** - Single video import + Bulk import with date range
2. **Schedule Tab** - Current schedule config
3. **Config Tab** - API key, video duration, AI settings
4. **Members Tab** - Current members section

Add import state and handlers:
```typescript
// Tab state
const [activeTab, setActiveTab] = useState<'import' | 'schedule' | 'config' | 'members'>('import');

// Import state
const [importUrl, setImportUrl] = useState('');
const [bulkStartDate, setBulkStartDate] = useState('');
const [bulkEndDate, setBulkEndDate] = useState('');
const [bulkMaxVideos, setBulkMaxVideos] = useState(10);
const [importProgress, setImportProgress] = useState<JobProgress | null>(null);

// Import handlers
const handleSingleImport = async () => {
    const res = await axios.post('/api/videos/import', {
        url: importUrl,
        channel_id: selectedChannelId
    });
    // Start polling job status
    pollJobStatus(res.data.job_id);
};

const handleBulkImport = async () => {
    const res = await axios.post('/api/videos/import-bulk', {
        channel_id: selectedChannelId,
        start_date: bulkStartDate,
        end_date: bulkEndDate,
        max_videos: bulkMaxVideos
    });
    // Start polling
};
```

Add 6-step progress tracker component:
```typescript
interface JobProgress {
    id: string;
    status: string;
    current_step: number;
    steps: Array<{
        name: string;
        status: 'pending' | 'running' | 'completed' | 'failed';
        progress?: number;
    }>;
}

const ProgressTracker = ({ progress }: { progress: JobProgress }) => (
    <div className="progress-tracker">
        {progress.steps.map((step, idx) => (
            <div key={idx} className={`progress-step ${step.status}`}>
                <div className={`step-icon ${step.status}`}>
                    {step.status === 'completed' ? '✓' :
                     step.status === 'running' ? '⟳' :
                     step.status === 'failed' ? '✗' : idx + 1}
                </div>
                <div className="step-info">
                    <span className="step-name">{step.name}</span>
                    {step.progress && (
                        <div className="step-progress-bar">
                            <div style={{ width: `${step.progress}%` }} />
                        </div>
                    )}
                </div>
            </div>
        ))}
    </div>
);
```

---

### Task 2.2: Members UI with Actions

Add to Admin.tsx members section:
```typescript
const [inviteModalOpen, setInviteModalOpen] = useState(false);
const [inviteEmail, setInviteEmail] = useState('');
const [inviteRole, setInviteRole] = useState('user');

const handleInvite = async () => {
    if (!inviteEmail.trim()) return;
    const res = await axios.post('/api/church/members/invite', {
        email: inviteEmail,
        role: inviteRole,
        channel_id: selectedChannelId
    });
    if (res.data.success) {
        alert('Membro adicionado!');
        setInviteModalOpen(false);
        setInviteEmail('');
        await loadAdminData();
    } else {
        alert(res.data.message);
    }
};

const handleRemoveMember = async (memberId: number) => {
    if (!confirm('Remover este membro?')) return;
    await axios.delete(`/api/church/members/${memberId}`);
    await loadAdminData();
};
```

---

### Task 2.3: API Key Config UI Section

Add to Admin.tsx config tab:
```typescript
const [geminiApiKey, setGeminiApiKey] = useState('');
const [currentApiKeyMasked, setCurrentApiKeyMasked] = useState('');
const [minVideoDuration, setMinVideoDuration] = useState(0);
const [maxVideoDuration, setMaxVideoDuration] = useState(180);

// In loadAdminData:
const apiConfigRes = await axios.get('/api/admin/settings/api-config');
setCurrentApiKeyMasked(apiConfigRes.data.gemini_api_key || '');

const durationRes = await axios.get('/api/admin/settings/video-duration');
setMinVideoDuration(durationRes.data.min_duration_minutes || 0);
setMaxVideoDuration(durationRes.data.max_duration_minutes || 180);

// UI Section:
<div className="config-section">
    <h3>🤖 Configuração de IA</h3>
    <div className="form-group">
        <label>Chave API Gemini</label>
        <input
            type="password"
            value={geminiApiKey}
            onChange={(e) => setGeminiApiKey(e.target.value)}
            placeholder={currentApiKeyMasked || 'Digite a chave API'}
        />
        {currentApiKeyMasked && <span className="hint">Atual: {currentApiKeyMasked}</span>}
    </div>
    <div className="form-group">
        <label>Duração Mínima (minutos)</label>
        <input type="number" value={minVideoDuration} onChange={...} />
    </div>
    <div className="form-group">
        <label>Duração Máxima (minutos)</label>
        <input type="number" value={maxVideoDuration} onChange={...} />
    </div>
    <button onClick={handleSaveConfig}>Salvar Configuração</button>
</div>
```

---

### Task 2.4: Knowledge Mode Toggle in Chat

**File:** `UI/src/stores/chatStore.ts`
```typescript
knowledgeMode: 'database_only' | 'global';
setKnowledgeMode: (mode: 'database_only' | 'global') => void;

// Initial state
knowledgeMode: 'database_only',
setKnowledgeMode: (mode) => set({ knowledgeMode: mode }),
```

**File:** `UI/src/services/chatService.ts`
```typescript
async sendMessage(
    channelId: string,
    message: string,
    sessionId: string,
    knowledgeMode: 'database_only' | 'global' = 'database_only'
): Promise<ChatResponseDTO> {
    const request: ChatRequestDTO = {
        message,
        session_id: sessionId,
        channel_id: channelId,
        knowledge_mode: knowledgeMode,
    };
    // ...
}
```

**File:** `UI/src/components/AIDrawer.tsx`
Add toggle buttons:
```typescript
<div className="knowledge-toggle">
    <button
        className={knowledgeMode === 'database_only' ? 'active' : ''}
        onClick={() => setKnowledgeMode('database_only')}
    >
        Somente sermões
    </button>
    <button
        className={knowledgeMode === 'global' ? 'active' : ''}
        onClick={() => setKnowledgeMode('global')}
    >
        Global / Internet
    </button>
</div>
```

---

## PHASE 3: HIGH PRIORITY

### Task 3.1: Drawer Resize (Restore from commit 0d697af)

**File:** `UI/src/hooks/useDrawerResize.ts` (NEW)
```typescript
import { useState, useEffect, useRef, useCallback } from 'react';

export function useDrawerResize(
    storageKey: string,
    defaultWidth: number,
    minWidth: number = 300,
    maxWidth: number = 800
) {
    const [width, setWidth] = useState(() => {
        const saved = localStorage.getItem(storageKey);
        return saved ? parseInt(saved, 10) : defaultWidth;
    });
    const [isResizing, setIsResizing] = useState(false);
    const startXRef = useRef(0);
    const startWidthRef = useRef(0);

    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        if (window.innerWidth <= 768) return;
        e.preventDefault();
        setIsResizing(true);
        startXRef.current = e.clientX;
        startWidthRef.current = width;
    }, [width]);

    useEffect(() => {
        if (!isResizing) return;

        const handleMouseMove = (e: MouseEvent) => {
            const delta = startXRef.current - e.clientX;
            const newWidth = Math.min(maxWidth, Math.max(minWidth, startWidthRef.current + delta));
            setWidth(newWidth);
        };

        const handleMouseUp = () => {
            setIsResizing(false);
            localStorage.setItem(storageKey, width.toString());
        };

        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);

        return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        };
    }, [isResizing, width, storageKey, minWidth, maxWidth]);

    return { width, isResizing, handleMouseDown };
}
```

**File:** `UI/src/styles/AIDrawer.css`
Add resize handle styles:
```css
.ai-drawer .resize-handle {
    position: absolute;
    left: 0;
    top: 0;
    width: 6px;
    height: 100%;
    cursor: ew-resize;
    background: transparent;
    z-index: 51;
    transition: background 0.2s;
}

.ai-drawer .resize-handle:hover,
.ai-drawer .resize-handle.active {
    background: rgba(59, 130, 246, 0.5);
}

.ai-drawer .resize-handle::after {
    content: '';
    position: absolute;
    left: 2px;
    top: 50%;
    transform: translateY(-50%);
    width: 2px;
    height: 40px;
    background: currentColor;
    border-radius: 1px;
    opacity: 0;
    transition: opacity 0.2s;
}

.ai-drawer .resize-handle:hover::after {
    opacity: 0.5;
}

.ai-drawer.resizing {
    transition: none !important;
}

@media (max-width: 768px) {
    .ai-drawer .resize-handle {
        display: none;
    }
}
```

**File:** `UI/src/components/AIDrawer.tsx`
```typescript
import { useDrawerResize } from '../hooks/useDrawerResize';

const { width: drawerWidth, isResizing, handleMouseDown } = useDrawerResize('chatbotPanelWidth', 400, 300, 800);

// In JSX:
<div
    className={`ai-drawer ${isOpen ? 'open' : ''} ${isResizing ? 'resizing' : ''}`}
    style={{ width: `${drawerWidth}px` }}
>
    <div className="resize-handle" onMouseDown={handleMouseDown} />
    {/* content */}
</div>
```

---

### Task 3.2: Push-Left Drawer Behavior

**File:** `UI/src/stores/chatStore.ts`
Export drawerWidth for VideoDetailDrawer:
```typescript
drawerWidth: number;
```

**File:** `UI/src/components/VideoDetailDrawer.tsx`
Adjust based on chatbot state:
```typescript
import { useChatStore } from '../stores/chatStore';

const { isOpen: chatbotOpen, drawerWidth: chatbotWidth } = useChatStore();

// Apply margin when chatbot is open
<div
    className="video-detail-drawer"
    style={{
        marginRight: chatbotOpen ? `${chatbotWidth}px` : 0,
        transition: 'margin-right 0.3s ease'
    }}
>
```

---

### Task 3.3: Settings Page Implementation

**File:** `UI/src/pages/Settings.tsx`
Full rewrite with password change functionality.

---

### Task 3.4: Profile Menu Expansion

**File:** `UI/src/components/TopAppBar.tsx`
Add "Configurações" link to dropdown before "Sair".

---

## PHASE 4: MEDIUM PRIORITY

### Task 4.1: Scheduler Status Widget

Add to Admin schedule section:
```typescript
const [schedulerStatus, setSchedulerStatus] = useState<{
    status: 'active' | 'inactive' | 'error';
    lastCheck: string | null;
    nextRun: string | null;
} | null>(null);

// Poll every 30 seconds
useEffect(() => {
    const fetchStatus = async () => {
        const res = await axios.get('/api/scheduler-status');
        setSchedulerStatus(res.data);
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
}, []);
```

---

### Task 4.2: Channel Header Banner

Add to top of Admin page:
```typescript
<div className="channel-banner">
    <h2>📺 {channelData?.title}</h2>
    <a href={channelData?.youtube_url} target="_blank">YouTube</a>
    <div className="stats">
        <span>📊 {stats?.totalVideos || 0} vídeos</span>
        <span>✅ {stats?.completedVideos || 0} processados</span>
    </div>
</div>
```

---

### Task 4.3: Contrast Fixes

**Search and replace in ALL files:**
`text-gray-400` → `text-gray-400 dark:text-gray-300`

Files: Login.tsx, Admin.tsx, VideoDetailDrawer.tsx, Reports.tsx, ChatMessage.tsx, Register.tsx, VideoListItem.tsx, MonthlyGroup.tsx, TopAppBar.tsx, Database.tsx, ProgressModal.tsx, VideoList.tsx

---

### Task 4.4: Routing Cleanup

**File:** `UI/src/App.tsx`
Remove `/channels` route.

**File:** `UI/src/components/TopAppBar.tsx`
Change nav link from `/channels` to `/`.

---

## Verification Checklist

### Admin Page - Import Tab
- [ ] Single video import by URL
- [ ] Bulk import with date range
- [ ] 6-step progress tracker displays
- [ ] Progress updates in real-time
- [ ] Job completion notification

### Admin Page - Config Tab
- [ ] API key input shows masked current
- [ ] Can save new API key
- [ ] Video duration min/max configurable
- [ ] Success message on save

### Admin Page - Members Tab
- [ ] Members table shows data
- [ ] "Convidar" modal opens
- [ ] Can add member by email
- [ ] Can remove member
- [ ] Per-channel member isolation

### AI Chatbot
- [ ] Knowledge toggle visible
- [ ] "Somente sermões" cites sermons
- [ ] "Global" answers general questions
- [ ] Drawer resizable (drag left edge)
- [ ] Width persists in localStorage
- [ ] Resize disabled on mobile

### Drawer Layout
- [ ] VideoDetailDrawer pushes left when chatbot opens
- [ ] Smooth transition animation
- [ ] Both drawers visible on wide screens

### Settings Page
- [ ] Shows user email
- [ ] Password change form works
- [ ] Validation errors shown
- [ ] Profile menu has "Configurações"

### Contrast
- [ ] All text readable in dark mode
- [ ] No gray-400 on dark backgrounds

---

## Deploy Steps

```bash
# 1. Build frontend
cd /Users/andrebyrro/Dev/CultoTranscript/UI && npm run build

# 2. Copy assets
scp -r dist/assets/* byrro@192.168.1.11:/home/byrro/CultoTranscript/app/web/static/assets/

# 3. Copy templates
scp app/web/templates/react_index.html byrro@192.168.1.11:/home/byrro/CultoTranscript/app/web/templates/index.html

# 4. Copy backend files
scp app/web/routes/api.py byrro@192.168.1.11:/home/byrro/CultoTranscript/app/web/routes/
scp Backend/api/v2/chat.py byrro@192.168.1.11:/home/byrro/CultoTranscript/Backend/api/v2/
scp Backend/dtos.py byrro@192.168.1.11:/home/byrro/CultoTranscript/Backend/

# 5. Restart
ssh byrro@192.168.1.11 "cd /home/byrro/CultoTranscript/docker && docker compose -p culto restart web"
```

---

## Parallel Agent Strategy

| Phase | Agent | Tasks |
|-------|-------|-------|
| 1 | Backend Agent | 1.1, 1.2, 1.3 (members, user, chat endpoints) |
| 2 | Admin UI Agent | 2.1, 2.2, 2.3 (tabs, import, members, config) |
| 2 | Chat UI Agent | 2.4 (knowledge toggle) |
| 3 | Drawer Agent | 3.1, 3.2 (resize, push-left) |
| 3 | Settings Agent | 3.3, 3.4 (settings page, profile menu) |
| 4 | Polish Agent | 4.1, 4.2, 4.3, 4.4 (scheduler widget, banner, contrast, routing) |
| Final | Validator | Browser testing ALL features |
