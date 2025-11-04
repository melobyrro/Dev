#!/bin/bash
#
# Run this script ON THE SERVER (192.168.1.11) to update the delete feature
#

cd /root/CultoTranscript

# Backup existing files
cp app/web/routes/api.py app/web/routes/api.py.backup
cp app/web/templates/index.html app/web/templates/index.html.backup

# Update api.py - add delete endpoint
cat >> app/web/routes/api.py << 'APIEOF'


@router.delete("/videos/{video_id}")
async def delete_video(
    video_id: int,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """
    Delete a video and all related data (transcript, verses, themes, jobs)

    The cascade delete is configured in SQLAlchemy relationships and database constraints.
    """
    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    try:
        # Delete the video (cascade will handle related records)
        db.delete(video)
        db.commit()

        return {
            "success": True,
            "message": f"Vídeo '{video.title}' excluído com sucesso"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao excluir vídeo: {str(e)}")
APIEOF

# Update index.html - replace the table section
python3 << 'PYEOF'
import re

# Read the file
with open('app/web/templates/index.html', 'r') as f:
    content = f.read()

# Update table header
content = re.sub(
    r'<thead>\s*<tr>\s*<th>Título</th>\s*<th>Status</th>\s*<th>Duração</th>\s*</tr>\s*</thead>',
    '''<thead>
                        <tr>
                            <th>Título</th>
                            <th>Status</th>
                            <th>Duração</th>
                            <th>Ações</th>
                        </tr>
                    </thead>''',
    content,
    flags=re.DOTALL
)

# Update table body to add delete button
content = re.sub(
    r"<td>\$\{Math\.floor\(v\.duration_sec / 60\)\} min</td>",
    '''<td>${Math.floor(v.duration_sec / 60)} min</td>
                                <td>
                                    <button onclick="deleteVideo(${v.id}, '${v.title.replace(/'/g, "\\\\'")}')"
                                            class="btn btn-secondary"
                                            style="padding: 0.3rem 0.6rem; font-size: 0.85rem;">
                                        Excluir
                                    </button>
                                </td>''',
    content
)

# Add delete function before loadRecentVideos()
content = re.sub(
    r'loadRecentVideos\(\);',
    '''// Delete video function
async function deleteVideo(videoId, title) {
    if (!confirm(`Tem certeza que deseja excluir o vídeo "${title}"?\\n\\nIsso irá remover permanentemente o vídeo, transcrição e todos os dados relacionados.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/videos/${videoId}`, {
            method: 'DELETE',
            headers: {'Content-Type': 'application/json'}
        });

        const data = await response.json();

        if (data.success) {
            alert(`Vídeo excluído com sucesso!`);
            loadRecentVideos(); // Reload the list
        } else {
            alert(`Erro ao excluir vídeo: ${data.detail || 'Erro desconhecido'}`);
        }
    } catch (error) {
        alert(`Erro ao excluir vídeo: ${error.message}`);
    }
}

loadRecentVideos();''',
    content
)

# Write back
with open('app/web/templates/index.html', 'w') as f:
    f.write(content)

print("✅ Updated index.html")
PYEOF

echo "✅ Files updated successfully"
echo "♻️  Restarting web service..."

cd docker
docker-compose restart web

echo "🎉 Update complete! Visit http://192.168.1.11:8000"
