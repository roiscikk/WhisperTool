# 🎙️ Whisper Tool: Professional Speech-to-Text Studio

An advanced, user-friendly desktop application powered by **OpenAI's Whisper** and **PyQt6**. This tool provides a seamless experience for transcribing audio/video, translating content, and recording live speech with high precision and hardware acceleration support.

---

<img width="901" height="723" alt="image" src="https://github.com/user-attachments/assets/5e1db9c1-d845-4eab-9ae8-311038a9afd8" />


## 🌍 Language Options / Dil Seçenekleri
- [English](#english)
- [Türkçe](#türkçe)

---

<a name="english"></a>
## 🇬🇧 English

### 🚀 Key Features
- **Multi-Model Support**: Access all OpenAI Whisper variants (`tiny` to `large-v3`).
- **Live Recording**: Built-in microphone support for real-time transcription.
- **Batch Processing**: Drag and drop multiple files or entire directories.
- **Advanced AI Processing**:
    - **VAD (Voice Activity Detection)**: Automatically filters out silence and background noise.
    - **Language Detection**: Automatically identifies the source language.
    - **Translation**: One-click translation from any supported language to English.
- **Modern & Customizable UI**:
    - **Dark Mode**: Eye-friendly interface for long sessions.
    - **Real-time Feedback**: Detailed progress bars and status updates.
- **Professional Exporting**: Save your work in `TXT`, `SRT` (Subtitles), `VTT`, `TSV`, or `JSON`.
- **Hardware Optimization**: Intelligent switching between **CPU** and **NVIDIA GPU (CUDA)**.

### 📊 Whisper Model Comparison
| Model | Parameters | VRAM Required | Relative Speed | Accuracy |
| :--- | :--- | :--- | :--- | :--- |
| **Tiny** | 39 M | ~1 GB | ~32x | Basic |
| **Base** | 74 M | ~1 GB | ~16x | Good |
| **Small** | 244 M | ~2 GB | ~6x | High |
| **Medium** | 769 M | ~5 GB | ~2x | Very High |
| **Large** | 1550 M | ~10 GB | 1x | State-of-the-Art |

### 🛠 Installation & Setup

> [!CAUTION]
> **CRITICAL REQUIREMENT:** **FFmpeg** must be installed and added to your system's PATH. Without FFmpeg, the application will fail to process any audio or video files.

#### 1. Prerequisites
- **Python 3.8+**
- **FFmpeg**:
    - **Windows**: `choco install ffmpeg` or download from [ffmpeg.org](https://ffmpeg.org/download.html)
    - **Linux**: `sudo apt install ffmpeg`
    - **macOS**: `brew install ffmpeg`

#### 2. Setup
```bash
# Clone the repository
git clone https://github.com/yourusername/WhisperTool.git
cd WhisperTool

# Install dependencies
pip install -r requirements.txt
```

### 📖 Usage Workflow
1. **Initialize**: Launch with `python main.py`.
2. **Input**: Click "Browse" or drag your files into the application.
3. **Configure**: Select the Model and options like VAD or Translation.
4. **Process**: Click "Transcribe". (Models download automatically on first use).
5. **Export**: Save your results via the Export menu.

---

<a name="türkçe"></a>
## 🇹🇷 Türkçe

### 🚀 Temel Özellikler
- **Çoklu Model Desteği**: Tüm OpenAI Whisper varyantlarına (`tiny`'den `large-v3`'e) erişim.
- **Canlı Kayıt**: Gerçek zamanlı deşifre için yerleşik mikrofon desteği.
- **Toplu İşleme**: Birden fazla dosyayı veya tüm dizinleri sürükleyip bırakın.
- **Gelişmiş Yapay Zeka İşleme**: VAD, Dil Algılama ve İngilizceye Çeviri.
- **Modern Arayüz**: Karanlık mod desteği ve gerçek zamanlı ilerleme takibi.
- **Profesyonel Dışa Aktarma**: `TXT`, `SRT`, `VTT`, `TSV` veya `JSON` desteği.
- **Donanım Optimizasyonu**: CPU ve NVIDIA GPU (CUDA) desteği.

### 📊 Whisper Model Karşılaştırması
| Model | Parametre | Gerekli VRAM | Göreceli Hız | Doğruluk |
| :--- | :--- | :--- | :--- | :--- |
| **Tiny** | 39 M | ~1 GB | ~32x | Temel |
| **Base** | 74 M | ~1 GB | ~16x | İyi |
| **Small** | 244 M | ~2 GB | ~6x | Yüksek |
| **Medium** | 769 M | ~5 GB | ~2x | Çok Yüksek |
| **Large** | 1550 M | ~10 GB | 1x | En Üst Düzey |

### 🛠 Kurulum ve Yapılandırma

> [!IMPORTANT]
> **KRİTİK GEREKSİNİM:** Sisteminize **FFmpeg** kurulu olmalıdır. FFmpeg yüklü değilse program ses dosyalarını işleyemez.

#### 1. Gereksinimler
- **Python 3.8+**
- **FFmpeg**:
    - **Windows**: `choco install ffmpeg` veya [ffmpeg.org](https://ffmpeg.org/download.html) üzerinden indirip PATH'e ekleyin.
    - **Linux**: `sudo apt install ffmpeg`
    - **macOS**: `brew install ffmpeg`

#### 2. Yükleme
```bash
# Depoyu klonlayın
git clone https://github.com/yourusername/WhisperTool.git
cd WhisperTool

# Bağımlılıkları yükleyin
pip install -r requirements.txt
```

### 📖 Kullanım Akışı
1. **Başlatma**: `python main.py` komutu ile uygulamayı açın.
2. **Giriş**: Dosyalarınızı seçin veya sürükleyip bırakın.
3. **Yapılandırma**: Modelinizi ve VAD gibi ayarlarınızı seçin.
4. **İşleme**: "Transcribe" (Metne Dönüştür) butonuna tıklayın.
5. **Dışa Aktarma**: Sonuçları istediğiniz formatta kaydedin.

---

## 🛠 Tech Stack / Teknoloji Yığını
- **Frontend**: PyQt6
- **Engine**: OpenAI Whisper AI
- **Multimedia**: FFmpeg, SoundDevice

## 📜 License / Lisans
Distributed under the MIT License.
MIT Lisansı ile korunmaktadır.
