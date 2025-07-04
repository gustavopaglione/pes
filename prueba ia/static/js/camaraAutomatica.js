document.addEventListener("DOMContentLoaded", () => {
    const video = document.getElementById("video");
    const canvas = document.getElementById("canvas");
    const captureBtn = document.getElementById("capture");
    const resultDiv = document.getElementById("result");

    // Iniciar cámara
    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => {
            video.srcObject = stream;
        })
        .catch(error => {
            resultDiv.innerHTML = "❌ No se pudo acceder a la cámara.";
        });

    // Capturar imagen
    captureBtn.addEventListener("click", () => {
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        // Convertir el contenido del canvas a Blob tipo JPEG
        canvas.toBlob(blob => {
            const formData = new FormData();
            formData.append("foto", blob, "captura.jpg");

            fetch("/recognize", {
                method: "POST",
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.acceso) {
                    resultDiv.innerHTML = `<div class="text-green-600">✅ Bienvenido ${data.nombre}</div>`;
                } else {
                    resultDiv.innerHTML = `<div class="text-yellow-600">⚠️ ${data.mensaje || data.error}</div>`;
                }
            })
            .catch(err => {
                resultDiv.innerHTML = `<div class="text-red-600">❌ Error en el servidor.</div>`;
                console.error(err);
            });
        }, "image/jpeg"); // 👈 Asegura tipo JPEG
    });
});
