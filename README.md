# Portal Personal - Despliegue en Producción

Este proyecto Flask puede desplegarse en varios servicios gratuitos. Aquí te explico las mejores opciones:

## 🚀 Opciones de Despliegue Gratuito

### 1. **Render** (Recomendado - Más fácil)
- ✅ Gratuito para proyectos pequeños
- ✅ Soporte nativo para Python/Flask
- ✅ Base de datos opcional
- ✅ Dominio personalizado gratuito

**Pasos:**
1. Ve a [render.com](https://render.com) y regístrate
2. Conecta tu cuenta de GitHub
3. Crea un nuevo "Web Service"
4. Selecciona tu repositorio
5. Configura:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn wsgi:app`
6. ¡Listo! Tendrás una URL como `https://tu-proyecto.onrender.com`

### 2. **Railway**
- ✅ Muy fácil de usar
- ✅ Gratuito para hobby projects
- ✅ Despliegue directo desde GitHub

**Pasos:**
1. Ve a [railway.app](https://railway.app)
2. Conecta GitHub
3. Railway detectará automáticamente que es Python
4. Configura las variables de entorno si necesitas

### 3. **PythonAnywhere**
- ✅ Específicamente para Python
- ✅ Fácil para principiantes
- ✅ Soporte técnico bueno

**Pasos:**
1. Ve a [pythonanywhere.com](https://pythonanywhere.com)
2. Crea cuenta gratuita
3. Sube tus archivos por FTP o Git
4. Configura el WSGI

## 📁 Archivos Necesarios para Despliegue

Ya tienes preparados:
- ✅ `requirements.txt` - Dependencias
- ✅ `config.py` - Configuración
- ✅ `wsgi.py` - Punto de entrada para producción
- ✅ `app.py` - Actualizado para producción

## 🔧 Configuración Adicional

### Variables de Entorno (Opcional)
Si necesitas configurar algo específico, puedes agregar variables de entorno en el panel de tu servicio de hosting:

```
SECRET_KEY=tu-clave-secreta-super-segura
FLASK_ENV=production
```

### Dominio Personalizado
La mayoría de servicios gratuitos te dan un subdominio, pero puedes usar servicios como:
- **Cloudflare Pages** (gratuito)
- **Vercel** (gratuito)
- **Netlify** (gratuito)

## 📱 Acceso desde Móvil

Una vez desplegado, podrás acceder desde tu celular usando la URL que te dé el servicio. Todos los servicios mencionados son responsive, así que se verá perfecto en móvil.

## 🎯 Recomendación

**Empieza con Render** - es el más sencillo para principiantes y tiene buena documentación.

¿Necesitas ayuda con algún paso específico?