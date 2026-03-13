import pytest
import os
import sys
import numpy as np
import base64
import io
from PIL import Image
from unittest.mock import MagicMock, patch

# Adicionar o diretório raiz ao sys.path para importar os módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_server_imports():
    """test_server_imports — server.py importa sem erro"""
    import server
    assert server.app is not None

def test_vision_imports():
    """test_vision_imports — vision.py importa sem erro"""
    import vision
    assert vision.detector is not None

def test_frame_validation():
    """test_frame_validation — frame inválido levanta ValueError"""
    from vision import validate_frame
    
    with pytest.raises(ValueError, match="Frame inválido"):
        validate_frame(None)
    
    with pytest.raises(ValueError, match="Frame vazio"):
        validate_frame(np.array([]))
    
    # Frame válido
    assert validate_frame(np.zeros((100, 100, 3), dtype=np.uint8)) is True

@pytest.mark.asyncio
async def test_analyze_returns_dict():
    """test_analyze_returns_dict — função de análise retorna dict"""
    from fastapi.testclient import TestClient
    from server import app
    
    client = TestClient(app)
    
    # Criar uma imagem base64 fake
    img = Image.new('RGB', (100, 100), color='red')
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    with patch('server.model') as mock_model:
        mock_response = MagicMock()
        mock_response.text = "Mocked analysis"
        # Mocking the async call. In server.py we use asyncio.to_thread
        # but for mocking it depends on how it's called.
        # Since we use asyncio.to_thread(model.generate_content, ...),
        # mock_model.generate_content should be a regular function returning what we want.
        mock_model.generate_content.return_value = mock_response
        
        response = client.post("/analyze", json={"image": img_str})
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert data["status"] == "success"
        assert data["text"] == "Mocked analysis"

@pytest.mark.asyncio
async def test_gemini_fallback():
    """test_gemini_fallback — se Gemini falha, retorna mensagem padrão"""
    from fastapi.testclient import TestClient
    from server import app
    
    client = TestClient(app)
    
    # Testar quando model é None (não configurado)
    with patch('server.model', None):
        img_str = "fakebase64"
        response = client.post("/analyze", json={"image": img_str})
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "IA indisponível"
    
    # Testar quando model falha
    with patch('server.model') as mock_model:
        mock_model.generate_content.side_effect = Exception("API Error")
        img = Image.new('RGB', (10, 10))
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        response = client.post("/analyze", json={"image": img_str})
        assert response.status_code == 500
        assert "API Error" in response.json()["detail"]
