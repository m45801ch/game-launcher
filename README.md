# 我的本地遊戲啟動器

一款以 Tkinter 開發的 Windows 本地遊戲啟動器，支援海報牆、遊戲分類（一般 / 隱私 / 收藏 / 虛擬）、拖曳新增、Steam 資訊更新、圖片快取與批次管理等功能。

> **版本：v1.0**

---

## 功能特色

- **海報牆展示**：依序排列遊戲封面，支援自訂列數（2～8 列）與排序方式。
- **四種分類標籤**：
  - 🏠 一般 — 一般遊戲
  - 🔐 隱私 — 私隱遊戲（需輸入代碼才能進入）
  - ❤ 收藏 — 收藏夾遊戲
  - 🖥️ 虛擬 — 需要特殊環境的遊戲（Test Signing 模式）
- **拖曳新增**：直接把 `.EXE` 檔案拖曳到啟動器內即可加入遊戲。
- **批量管理**：批次移動遊戲到不同分類、批次備份資料庫。
- **Steam 資訊更新**：自動抓取 Steam 商店的評價、發行日期、開發人員與簡介。
- **圖片快取**：海報圖片快取到本地 `img_cache/`，避免重複載入。

---

## 下載與執行

### Release 下載

v1.0 的 Release 提供一個壓縮檔 `game_launcher_v1.0.zip`，解壓後包含：

```
game_launcher_v1.0/
├── game_launcher.exe     # 啟動器執行檔
├── TS_On.bat             # 開 Test Signing（管理員）
├── TS_Off.bat            # 關 Test Signing（管理員）
└── README.md             # 說明文件
```

> **注意**：解壓後請**從 `game_launcher.exe` 所在目錄內啟動**，這樣才能讀到同目錄的 `games.json`、`config.json` 與 `img_cache/`。若從別的目錄啟動，游戲清單會是空的。

---

## 虛擬模式（Test Signing）

本機的 VBS 模式無法使用，因此虛擬分類改為 **Test Signing** 方式：

1. 玩遊戲前：按「① 開 Test Signing」執行 `TS_On.bat`（會跳出 UAC，請以管理員執行）
2. 重新開機 → 桌面出現「測試模式 / Test Mode」浮水印即屬正常 → 再啟動遊戲
3. 玩完遊戲後：按「② 關 Test Signing」執行 `TS_Off.bat`（管理員）
4. 重新開機 → 恢復正常模式，浮水印消失

> 開／關都必須重開機才會生效。按鈕左鍵執行、右鍵可更換批次檔路徑。

---

## 打包為執行檔

使用 PyInstaller 將 `game_launcher.py` 打包為 Windows 執行檔：

```powershell
python -m PyInstaller --noconfirm game_launcher.spec
```

打包完成後，執行檔會生成在 `dist/` 資料夾中（`game_launcher.exe`）。

> 執行時請**從 `game_launcher.exe` 所在目錄內啟動**，這樣才能讀到同目錄的 `games.json`、`config.json` 與 `img_cache/`。

---

## 檔案結構

```
game_launcher/
├── game_launcher.py          # 主程式
├── game_launcher.spec        # PyInstaller 打包設定
├── TS_On.bat                 # 開 Test Signing（管理員）
├── TS_Off.bat                # 關 Test Signing（管理員）
├── .gitignore                # 排除敏感档案
└── README.md                 # 本說明
```

> 個人資料（`games.json`、`config.json`、`img_cache/`、打包產物）已列入 `.gitignore`，不會上傳。

---

## 備註

- 本專案為個人專案，程式碼中可能包含個人的游戏清單與設定。
- 開發環境：Python 3.14 + tkinter + tkinterdnd2 + tkinterweb + Pillow + requests + BeautifulSoup。