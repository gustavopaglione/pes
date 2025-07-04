console.log("biometric.js cargado");

document.addEventListener('DOMContentLoaded', function() {
    // Elementos del DOM
    const video = document.getElementById('videoElement');
    const fingerprintBtn = document.getElementById('scanFingerprint');
    const faceBtn = document.getElementById('scanFace');
    const scanResults = document.getElementById('scanResults');
    const faceCamera = document.getElementById('faceCameraContainer');
    const userForm = document.getElementById('userForm');
    
    // Estados
    let stream = null;
    let faceRegistered = false;
    let fingerprintRegistered = false;
    let capturedFaceBlob = null;

    // 1. Configuración inicial de la cámara
    async function initCamera() {
        // Limpiar contenedor primero
        faceCamera.innerHTML = '';
        
        // Verificar compatibilidad
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            showCameraError("Navegador no compatible con la API de medios");
            return;
        }

        try {
            // Configurar cámara
            const mediaStream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: 'user',
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                },
                audio: false
            });

            stream = mediaStream;
            
            // Configurar elemento de video
            video.srcObject = stream;
            video.classList.remove('hidden');
            
            // Mostrar video en el contenedor
            faceCamera.appendChild(video);
            
            // Esperar a que el video esté listo
            await new Promise((resolve) => {
                video.onloadedmetadata = () => {
                    video.play().then(resolve).catch(err => {
                        showCameraError("Error al reproducir video: " + err.message);
                    });
                };
            });
            
            // Mostrar mensaje de guía
            const guide = document.createElement('div');
            guide.className = 'absolute bottom-2 left-0 right-0 text-center text-white text-sm bg-black bg-opacity-50 p-1';
            guide.textContent = 'Posicione su rostro dentro del área marcada';
            faceCamera.appendChild(guide);
            
            // Dibujar overlay de guía para el rostro
            drawFaceGuide();
            
        } catch (error) {
            showCameraError("Error al acceder a la cámara: " + error.message);
            console.error("Error de cámara:", error);
        }
    }

    function drawFaceGuide() {
        const overlay = document.createElement('div');
        overlay.className = 'absolute inset-0 flex items-center justify-center pointer-events-none';
        
        const guide = document.createElement('div');
        guide.className = 'w-40 h-56 border-2 border-blue-400 rounded-full opacity-70';
        guide.style.boxShadow = '0 0 20px rgba(59, 130, 246, 0.7)';
        
        overlay.appendChild(guide);
        faceCamera.appendChild(overlay);
    }

    function showCameraError(message) {
        faceCamera.innerHTML = `
            <div class="w-full h-full flex flex-col items-center justify-center bg-gray-200 rounded-lg">
                <i class="fas fa-video-slash text-5xl text-red-500 mb-3"></i>
                <p class="text-red-600 font-medium">${message}</p>
                <button id="retryCamera" class="mt-4 bg-blue-600 text-white px-4 py-2 rounded-lg">
                    <i class="fas fa-sync-alt mr-2"></i> Reintentar
                </button>
            </div>
        `;
        
        document.getElementById('retryCamera')?.addEventListener('click', initCamera);
    }

    // 2. Captura de rostro
    faceBtn.addEventListener('click', async function() {
        if (faceRegistered) return;
        
        try {
            // Cambiar estado del botón
            this.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Procesando...';
            this.disabled = true;
            
            // Crear canvas para captura
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            
            // Ajustar tamaño del canvas al video
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            
            // Dibujar el frame actual del video en el canvas
            context.drawImage(video, 0, 0, canvas.width, canvas.height);
            
            // Convertir a blob (formato JPEG con 90% de calidad)
            capturedFaceBlob = await new Promise((resolve) => {
                canvas.toBlob(resolve, 'image/jpeg', 0.9);
            });
            
            // Mostrar imagen capturada
            faceCamera.innerHTML = '';
            const img = new Image();
            img.src = URL.createObjectURL(capturedFaceBlob);
            img.className = 'w-full h-full object-cover rounded-lg';
            faceCamera.appendChild(img);
            
            // Actualizar UI
            this.innerHTML = '<i class="fas fa-check-circle mr-2"></i> Rostro registrado';
            this.classList.remove('bg-blue-600', 'hover:bg-blue-700');
            this.classList.add('bg-green-600', 'hover:bg-green-700');
            
            // Mostrar resultados
            scanResults.classList.remove('hidden');
            faceRegistered = true;
            
        } catch (error) {
            console.error("Error en captura facial:", error);
            this.innerHTML = '<i class="fas fa-camera mr-2"></i> Capturar Rostro';
            this.disabled = false;
            alert(`Error: ${error.message}`);
        }
    });

    // 3. Escaneo de huella digital (simulación)
    fingerprintBtn.addEventListener('click', function() {
        if (fingerprintRegistered) return;
        
        this.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Escaneando...';
        this.disabled = true;
        
        // Simular escaneo de huella (3 segundos)
        setTimeout(() => {
            this.innerHTML = '<i class="fas fa-check-circle mr-2"></i> Huella registrada';
            this.classList.remove('bg-blue-600', 'hover:bg-blue-700');
            this.classList.add('bg-green-600', 'hover:bg-green-700');
            
            // Actualizar icono de huella
            const fingerprintIcon = document.querySelector('.fa-fingerprint');
            fingerprintIcon.classList.remove('text-gray-400');
            fingerprintIcon.classList.add('text-blue-500', 'pulse');
            
            // Mostrar resultados
            scanResults.classList.remove('hidden');
            fingerprintRegistered = true;
        }, 3000);
    });

    // 4. Manejo del formulario
    userForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Validar campos
        const firstName = document.getElementById('firstName').value.trim();
        const lastName = document.getElementById('lastName').value.trim();
        const idNumber = document.getElementById('idNumber').value.trim();
        
        if (!firstName || !lastName || !idNumber) {
            alert('Por favor complete todos los campos obligatorios');
            return;
        }
        
        if (!fingerprintRegistered || !faceRegistered) {
            alert('Por favor complete ambos escaneos biométricos');
            return;
        }
        
        try {
            // Crear FormData para enviar al servidor
            const formData = new FormData();
            formData.append('firstName', firstName);
            formData.append('lastName', lastName);
            formData.append('idNumber', idNumber);
            formData.append('department', document.getElementById('department').value);
            formData.append('accessType', document.querySelector('input[name="access-type"]:checked').value);
            formData.append('faceImage', capturedFaceBlob, 'face.jpg');  // ¡Importante: el nombre debe coincidir con el del backend!

            const response = await fetch('/api/register', {
                method: 'POST',
                body: formData  // No incluir headers 'Content-Type' para FormData
            });
            
            if (!response.ok) {
                throw new Error('Error en el servidor');
            }
            
            const result = await response.json();
            
            if (result.success) {
                // Mostrar modal de confirmación
                document.getElementById('modalTitle').textContent = 'Registro exitoso';
                document.getElementById('confirmationModal').classList.remove('hidden');
            } else {
                throw new Error(result.message || 'Error al registrar');
            }
            
        } catch (error) {
            console.error('Error al enviar datos:', error);
            alert('Error al registrar: ' + error.message);
        }
    });

    // 5. Funciones de utilidad
    function stopCamera() {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            stream = null;
        }
    }

    function resetForm() {
        // Resetear formulario
        userForm.reset();
        
        // Resetear estados biométricos
        faceRegistered = false;
        fingerprintRegistered = false;
        capturedFaceBlob = null;
        
        // Resetear botones
        faceBtn.innerHTML = '<i class="fas fa-camera mr-2"></i> Capturar Rostro';
        faceBtn.disabled = false;
        faceBtn.classList.remove('bg-green-600', 'hover:bg-green-700');
        faceBtn.classList.add('bg-blue-600', 'hover:bg-blue-700');
        
        fingerprintBtn.innerHTML = '<i class="fas fa-play mr-2"></i> Iniciar Escaneo';
        fingerprintBtn.disabled = false;
        fingerprintBtn.classList.remove('bg-green-600', 'hover:bg-green-700');
        fingerprintBtn.classList.add('bg-blue-600', 'hover:bg-blue-700');
        
        // Resetear icono de huella
        const fingerprintIcon = document.querySelector('.fa-fingerprint');
        fingerprintIcon.classList.remove('text-blue-500', 'pulse');
        fingerprintIcon.classList.add('text-gray-400');
        
        // Ocultar resultados
        scanResults.classList.add('hidden');
        
        // Reiniciar cámara
        initCamera();
    }

    // 6. Configurar botón de confirmación del modal
    document.getElementById('confirmButton').addEventListener('click', function() {
        document.getElementById('confirmationModal').classList.add('hidden');
        resetForm();
    });

    // Inicializar cámara al cargar
    initCamera();
});

