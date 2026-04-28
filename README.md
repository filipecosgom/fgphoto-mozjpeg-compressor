# MozJPEG Compressor

Interface gráfica para comprimir imagens JPEG e PNG com MozJPEG no Windows.

## Requisitos

- Windows 10 ou superior (64-bit)
- Python 3.10 ou superior → https://python.org
- Ligação à internet (apenas no primeiro arranque, para descarregar o MozJPEG)

## Como usar

### Primeira vez

1. Faz duplo clique em **`arrancar.bat`**
2. Aguarda a instalação das dependências Python
3. A app arranca e detecta automaticamente se o MozJPEG está instalado
4. Se não estiver, abre uma janela de download — clica OK e aguarda

### Uso normal

1. Seleciona a pasta de origem com o botão 📁
2. Activa "Incluir subpastas" se quiseres processar recursivamente
3. Ajusta a **Qualidade** (80 é um bom ponto de partida para web)
4. Expande **Definições avançadas** se quiseres controlo total
5. Clica **Procurar ficheiros** para listar as imagens encontradas
6. Clica **Iniciar compressão** para começar

### Resultado

Os ficheiros comprimidos ficam numa pasta **`export`** criada dentro da pasta de origem.  
O nome inclui o valor de qualidade: `foto_compressed_80.jpg`

Clica em qualquer ficheiro da lista para ver a comparação original vs. comprimido no painel inferior.

## Definições avançadas

| Definição | O que faz |
|---|---|
| JPEG Progressivo | Imagem carrega gradualmente em browsers |
| Otimizar Huffman | Reduz tamanho 3–5% sem perda de qualidade |
| Escala de cinzentos | Remove cor, converte para monocromático |
| Subamostragem | Como a cor é armazenada (4:2:0 recomendado para web) |
| Método DCT | Algoritmo de compressão (`int` recomendado) |
| Tabela de quantização | `1` usa tabela optimizada do MozJPEG |
| Suavização | Suaviza antes de comprimir (útil para imagens com ruído) |

## Skip inteligente

Se já comprimiste uma pasta a 80% e voltares a correr com 80%, os ficheiros existentes são ignorados.  
Se mudares para 70%, os novos ficheiros têm sufixo `_compressed_70.jpg` e são processados normalmente.

## Localização do MozJPEG

O binário é guardado em:  
`%APPDATA%\MozJPEGCompressor\bin\cjpeg.exe`
