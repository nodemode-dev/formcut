const codes = ["fr", "it", "ja", "ko", "pt-BR", "ru", "tr", "zh-Hans", "zh-Hant"];
const rows = `Media|Médias|Media|メディア|미디어|Mídia|Медиа|Medya|媒体|媒體
Video effects|Effets vidéo|Effetti video|動画エフェクト|비디오 효과|Efeitos de vídeo|Видеоэффекты|Video efektleri|视频效果|影片效果
Audio effects|Effets audio|Effetti audio|オーディオエフェクト|오디오 효과|Efeitos de áudio|Аудиоэффекты|Ses efektleri|音频效果|音訊效果
Blur|Flou|Sfocatura|ぼかし|흐림|Desfoque|Размытие|Bulanıklık|模糊|模糊
Stylize|Stylisation|Stilizzazione|スタイライズ|스타일화|Estilização|Стилизация|Stilize|风格化|風格化
Distort|Déformation|Distorsione|ゆがみ|왜곡|Distorção|Искажение|Bozulma|扭曲|扭曲
Texture|Texture|Texture|テクスチャ|텍스처|Textura|Текстура|Doku|纹理|紋理
Cutout|Détourage|Scontorno|切り抜き|오려내기|Recorte|Вырезание|Dekupe|抠像|去背
Tone|Tonalité|Tono|トーン|톤|Tom|Тон|Ton|音色|音色
Space|Espace|Spazio|空間|공간|Espaço|Пространство|Mekân|空间|空間
Clean|Nettoyage|Pulizia|クリーンアップ|정리|Limpeza|Очистка|Temizleme|清理|清理
Film|Film|Pellicola|フィルム|필름|Filme|Плёнка|Film|胶片|膠片
Warm|Chaud|Caldo|暖色|따뜻한 톤|Quente|Тёплые|Sıcak|暖色|暖色
Cool|Froid|Freddo|寒色|차가운 톤|Frio|Холодные|Soğuk|冷色|冷色
Split|Virage partiel|Viraggio diviso|スプリットトーン|스플릿 톤|Tonalização dividida|Раздельное тонирование|Bölünmüş ton|分离色调|分離色調
Basic|Base|Base|基本|기본|Básico|Основное|Temel|基础|基本
Animation|Animation|Animazione|アニメーション|애니메이션|Animação|Анимация|Animasyon|动画|動畫
Adjust|Réglages|Regolazioni|調整|조정|Ajustar|Настройка|Ayarlar|调整|調整
Focus preview|Mettre l'aperçu en avant|Anteprima in primo piano|プレビューに集中|미리보기 집중|Focar na pré-visualização|Фокус на предпросмотре|Önizlemeye odaklan|专注预览|專注預覽
Studio|Studio|Studio|スタジオ|스튜디오|Estúdio|Студия|Stüdyo|工作室|工作室
saved|enregistré|salvato|保存済み|저장됨|salvo|сохранено|kaydedildi|已保存|已儲存
edited|modifié|modificato|編集済み|수정됨|editado|изменено|düzenlendi|已编辑|已編輯
Start|Début|Inizio|先頭へ|처음으로|Início|В начало|Başa git|跳到开头|跳到開頭
Previous frame|Image précédente|Fotogramma precedente|前のフレーム|이전 프레임|Quadro anterior|Предыдущий кадр|Önceki kare|上一帧|上一格
Play or pause|Lecture ou pause|Riproduci o pausa|再生/一時停止|재생 또는 일시정지|Reproduzir ou pausar|Воспроизведение или пауза|Oynat veya duraklat|播放或暂停|播放或暫停
Next frame|Image suivante|Fotogramma successivo|次のフレーム|다음 프레임|Próximo quadro|Следующий кадр|Sonraki kare|下一帧|下一格
End|Fin|Fine|末尾へ|끝으로|Fim|В конец|Sona git|跳到结尾|跳到結尾
Video preview|Aperçu vidéo|Anteprima video|動画プレビュー|비디오 미리보기|Pré-visualização do vídeo|Предпросмотр видео|Video önizlemesi|视频预览|影片預覽
Preview resolution|Résolution de l'aperçu|Risoluzione dell'anteprima|プレビュー解像度|미리보기 해상도|Resolução da pré-visualização|Разрешение предпросмотра|Önizleme çözünürlüğü|预览分辨率|預覽解析度
Remove track|Supprimer la piste|Rimuovi traccia|トラックを削除|트랙 삭제|Remover trilha|Удалить дорожку|Parçayı kaldır|删除轨道|刪除軌道
Lock track|Verrouiller la piste|Blocca traccia|トラックをロック|트랙 잠금|Bloquear trilha|Заблокировать дорожку|Parçayı kilitle|锁定轨道|鎖定軌道
Hide track|Masquer la piste|Nascondi traccia|トラックを非表示|트랙 숨기기|Ocultar trilha|Скрыть дорожку|Parçayı gizle|隐藏轨道|隱藏軌道
Mute track|Couper le son de la piste|Silenzia traccia|トラックをミュート|트랙 음소거|Silenciar trilha|Заглушить дорожку|Parçanın sesini kapat|静音轨道|靜音軌道
Magnetic track|Piste magnétique|Traccia magnetica|マグネットトラック|자석 트랙|Trilha magnética|Магнитная дорожка|Mıknatıslı parça|磁性轨道|磁性軌道
Double-click to rename track|Double-cliquez pour renommer la piste|Doppio clic per rinominare la traccia|ダブルクリックでトラック名を変更|두 번 클릭하여 트랙 이름 바꾸기|Clique duas vezes para renomear a trilha|Дважды щёлкните, чтобы переименовать дорожку|Yeniden adlandırmak için çift tıklayın|双击以重命名轨道|按兩下以重新命名軌道
Scrub playhead|Déplacer la tête de lecture|Trascina la testina|再生ヘッドをドラッグ|재생 헤드 이동|Arrastar o cursor de reprodução|Перемещение указателя воспроизведения|Oynatma kafasını sürükle|拖动播放头|拖曳播放頭
Timeline height|Hauteur de la timeline|Altezza della timeline|タイムラインの高さ|타임라인 높이|Altura da linha do tempo|Высота таймлайна|Zaman çizelgesi yüksekliği|时间线高度|時間軸高度
Resize selected clip nw|Redimensionner le clip sélectionné (coin supérieur gauche)|Ridimensiona la clip selezionata (angolo in alto a sinistra)|選択したクリップのサイズを変更（左上）|선택한 클립 크기 조정(왼쪽 위)|Redimensionar o clipe selecionado (canto superior esquerdo)|Изменить размер выбранного клипа (левый верхний угол)|Seçili klibi yeniden boyutlandır (sol üst)|调整所选片段大小（左上）|調整所選片段大小（左上）
Resize selected clip n|Redimensionner le clip sélectionné (bord supérieur)|Ridimensiona la clip selezionata (lato superiore)|選択したクリップのサイズを変更（上）|선택한 클립 크기 조정(위)|Redimensionar o clipe selecionado (borda superior)|Изменить размер выбранного клипа (верхний край)|Seçili klibi yeniden boyutlandır (üst)|调整所选片段大小（上）|調整所選片段大小（上）
Resize selected clip ne|Redimensionner le clip sélectionné (coin supérieur droit)|Ridimensiona la clip selezionata (angolo in alto a destra)|選択したクリップのサイズを変更（右上）|선택한 클립 크기 조정(오른쪽 위)|Redimensionar o clipe selecionado (canto superior direito)|Изменить размер выбранного клипа (правый верхний угол)|Seçili klibi yeniden boyutlandır (sağ üst)|调整所选片段大小（右上）|調整所選片段大小（右上）
Resize selected clip e|Redimensionner le clip sélectionné (bord droit)|Ridimensiona la clip selezionata (lato destro)|選択したクリップのサイズを変更（右）|선택한 클립 크기 조정(오른쪽)|Redimensionar o clipe selecionado (borda direita)|Изменить размер выбранного клипа (правый край)|Seçili klibi yeniden boyutlandır (sağ)|调整所选片段大小（右）|調整所選片段大小（右）
Resize selected clip se|Redimensionner le clip sélectionné (coin inférieur droit)|Ridimensiona la clip selezionata (angolo in basso a destra)|選択したクリップのサイズを変更（右下）|선택한 클립 크기 조정(오른쪽 아래)|Redimensionar o clipe selecionado (canto inferior direito)|Изменить размер выбранного клипа (правый нижний угол)|Seçili klibi yeniden boyutlandır (sağ alt)|调整所选片段大小（右下）|調整所選片段大小（右下）
Resize selected clip s|Redimensionner le clip sélectionné (bord inférieur)|Ridimensiona la clip selezionata (lato inferiore)|選択したクリップのサイズを変更（下）|선택한 클립 크기 조정(아래)|Redimensionar o clipe selecionado (borda inferior)|Изменить размер выбранного клипа (нижний край)|Seçili klibi yeniden boyutlandır (alt)|调整所选片段大小（下）|調整所選片段大小（下）
Resize selected clip sw|Redimensionner le clip sélectionné (coin inférieur gauche)|Ridimensiona la clip selezionata (angolo in basso a sinistra)|選択したクリップのサイズを変更（左下）|선택한 클립 크기 조정(왼쪽 아래)|Redimensionar o clipe selecionado (canto inferior esquerdo)|Изменить размер выбранного клипа (левый нижний угол)|Seçili klibi yeniden boyutlandır (sol alt)|调整所选片段大小（左下）|調整所選片段大小（左下）
Resize selected clip w|Redimensionner le clip sélectionné (bord gauche)|Ridimensiona la clip selezionata (lato sinistro)|選択したクリップのサイズを変更（左）|선택한 클립 크기 조정(왼쪽)|Redimensionar o clipe selecionado (borda esquerda)|Изменить размер выбранного клипа (левый край)|Seçili klibi yeniden boyutlandır (sol)|调整所选片段大小（左）|調整所選片段大小（左）
Rotate selected clip|Faire pivoter le clip sélectionné|Ruota la clip selezionata|選択したクリップを回転|선택한 클립 회전|Girar o clipe selecionado|Повернуть выбранный клип|Seçili klibi döndür|旋转所选片段|旋轉所選片段
Move selected clip|Déplacer le clip sélectionné|Sposta la clip selezionata|選択したクリップを移動|선택한 클립 이동|Mover o clipe selecionado|Переместить выбранный клип|Seçili klibi taşı|移动所选片段|移動所選片段
Media panel|Panneau Médias|Pannello Media|メディアパネル|미디어 패널|Painel de mídia|Панель медиа|Medya paneli|媒体面板|媒體面板
Inspector panel|Panneau Inspecteur|Pannello Ispettore|インスペクターパネル|인스펙터 패널|Painel do inspetor|Панель инспектора|Denetçi paneli|检查器面板|檢閱器面板
Timeline panel|Panneau Timeline|Pannello Timeline|タイムラインパネル|타임라인 패널|Painel da linha do tempo|Панель таймлайна|Zaman çizelgesi paneli|时间线面板|時間軸面板
Reset layout|Réinitialiser la disposition|Ripristina layout|レイアウトをリセット|레이아웃 초기화|Redefinir layout|Сбросить макет|Düzeni sıfırla|重置布局|重設版面配置
Short timeline|Timeline basse|Timeline bassa|タイムライン（低）|낮은 타임라인|Linha do tempo baixa|Низкий таймлайн|Kısa zaman çizelgesi|矮时间线|矮時間軸
Medium timeline|Timeline moyenne|Timeline media|タイムライン（中）|중간 타임라인|Linha do tempo média|Средний таймлайн|Orta zaman çizelgesi|中等时间线|中等時間軸
Tall timeline|Timeline haute|Timeline alta|タイムライン（高）|높은 타임라인|Linha do tempo alta|Высокий таймлайн|Uzun zaman çizelgesi|高时间线|高時間軸
Undo|Annuler|Annulla|元に戻す|실행 취소|Desfazer|Отменить|Geri al|撤销|復原
Redo|Rétablir|Ripeti|やり直し|다시 실행|Refazer|Повторить|Yinele|重做|取消復原
Copy clip|Copier le clip|Copia clip|クリップをコピー|클립 복사|Copiar clipe|Копировать клип|Klibi kopyala|复制片段|複製片段
Paste clip|Coller le clip|Incolla clip|クリップを貼り付け|클립 붙여넣기|Colar clipe|Вставить клип|Klibi yapıştır|粘贴片段|貼上片段
Duplicate clip|Dupliquer le clip|Duplica clip|クリップを複製|클립 복제|Duplicar clipe|Дублировать клип|Klibi çoğalt|创建片段副本|再製片段
Delete clip|Supprimer le clip|Elimina clip|クリップを削除|클립 삭제|Excluir clipe|Удалить клип|Klibi sil|删除片段|刪除片段
Fullscreen|Plein écran|Schermo intero|全画面表示|전체 화면|Tela cheia|Полноэкранный режим|Tam ekran|全屏|全螢幕
Add point at playhead|Ajouter un point à la tête de lecture|Aggiungi punto alla testina|再生ヘッドにポイントを追加|재생 헤드에 점 추가|Adicionar ponto no cursor de reprodução|Добавить точку у указателя|Oynatma kafasına nokta ekle|在播放头处添加点|在播放頭處新增點
Preset|Préréglage|Preset|プリセット|프리셋|Predefinição|Пресет|Hazır ayar|预设|預設集
Select a clip to edit its tools|Sélectionnez un clip pour modifier ses outils|Seleziona una clip per modificarne gli strumenti|クリップを選択してツールを編集|클립을 선택하여 도구를 편집하세요|Selecione um clipe para editar suas ferramentas|Выберите клип, чтобы изменить его инструменты|Araçlarını düzenlemek için bir klip seçin|选择一个片段以编辑其工具|選取片段以編輯其工具
Creator tool|Outil de création|Strumento creativo|クリエイターツール|크리에이터 도구|Ferramenta de criação|Инструмент автора|Oluşturma aracı|创作工具|創作工具
Motion|Mouvement|Movimento|モーション|모션|Movimento|Движение|Hareket|运动|動態
Seconds|Secondes|Secondi|秒|초|Segundos|Секунды|Saniye|秒|秒
Chroma key|Incrustation chromatique|Chroma key|クロマキー|크로마 키|Chroma key|Хромакей|Kroma anahtarı|色度键|色度鍵
Remove last stroke|Supprimer le dernier trait|Rimuovi l'ultimo tratto|最後のストロークを削除|마지막 획 제거|Remover o último traço|Удалить последний штрих|Son fırça darbesini kaldır|移除最后一笔|移除最後一筆
Model|Modèle|Modello|モデル|모델|Modelo|Модель|Model|模型|模型
Threshold|Seuil|Soglia|しきい値|임계값|Limiar|Порог|Eşik|阈值|閾值
Edge softness|Douceur des bords|Morbidezza dei bordi|エッジの柔らかさ|가장자리 부드러움|Suavidade da borda|Мягкость края|Kenar yumuşaklığı|边缘柔和度|邊緣柔和度
Brush|Pinceau|Pennello|ブラシ|브러시|Pincel|Кисть|Fırça|画笔|筆刷
Brush radius|Rayon du pinceau|Raggio del pennello|ブラシの半径|브러시 반경|Raio do pincel|Радиус кисти|Fırça yarıçapı|画笔半径|筆刷半徑
Paint on the preview. Brush edits use source coordinates and are saved with the clip.|Peignez sur l'aperçu. Les retouches au pinceau utilisent les coordonnées de la source et sont enregistrées avec le clip.|Dipingi sull'anteprima. Le modifiche con il pennello usano le coordinate della sorgente e vengono salvate con la clip.|プレビュー上で描画します。ブラシの編集はソースの座標を使用し、クリップと一緒に保存されます。|미리보기에 칠하세요. 브러시 편집은 원본 좌표를 사용하며 클립과 함께 저장됩니다.|Pinte na pré-visualização. As edições com pincel usam as coordenadas da origem e são salvas com o clipe.|Рисуйте на предпросмотре. Правки кистью используют координаты исходника и сохраняются вместе с клипом.|Önizlemenin üzerine boyayın. Fırça düzenlemeleri kaynak koordinatlarını kullanır ve klip ile birlikte kaydedilir.|在预览上绘制。画笔编辑使用源坐标，并随片段一起保存。|在預覽上繪製。筆刷編輯使用來源座標，並隨片段一起儲存。
Mute clip|Couper le son du clip|Silenzia clip|クリップをミュート|클립 음소거|Silenciar clipe|Заглушить клип|Klibin sesini kapat|静音片段|靜音片段
Processor|Processeur|Processore|プロセッサー|프로세서|Processador|Обработка|İşlemci|处理器|處理器
Effect|Effet|Effetto|エフェクト|효과|Efeito|Эффект|Efekt|效果|效果
Remove active timeline|Supprimer la timeline active|Rimuovi la timeline attiva|アクティブなタイムラインを削除|활성 타임라인 삭제|Remover a linha do tempo ativa|Удалить активный таймлайн|Etkin zaman çizelgesini kaldır|删除当前时间线|刪除目前的時間軸
Studio tools|Outils du studio|Strumenti dello studio|スタジオツール|스튜디오 도구|Ferramentas do estúdio|Инструменты студии|Stüdyo araçları|工作室工具|工作室工具
Timeline structure|Structure de la timeline|Struttura della timeline|タイムラインの構成|타임라인 구조|Estrutura da linha do tempo|Структура таймлайна|Zaman çizelgesi yapısı|时间线结构|時間軸結構
Frame rate|Fréquence d'images|Frequenza fotogrammi|フレームレート|프레임 속도|Taxa de quadros|Частота кадров|Kare hızı|帧率|影格速率
Name|Nom|Nome|名前|이름|Nome|Имя|Ad|名称|名稱
Active timeline|Timeline active|Timeline attiva|アクティブなタイムライン|활성 타임라인|Linha do tempo ativa|Активный таймлайн|Etkin zaman çizelgesi|当前时间线|目前的時間軸
All settings and structure changes support Undo.|Tous les réglages et changements de structure peuvent être annulés.|Tutte le impostazioni e le modifiche alla struttura si possono annullare.|すべての設定と構成の変更は元に戻せます。|모든 설정 및 구조 변경은 실행 취소할 수 있습니다.|Todas as configurações e mudanças de estrutura podem ser desfeitas.|Все изменения настроек и структуры можно отменить.|Tüm ayar ve yapı değişiklikleri geri alınabilir.|所有设置和结构更改均可撤销。|所有設定和結構變更皆可復原。
Save current project as template|Enregistrer le projet actuel comme modèle|Salva il progetto attuale come modello|現在のプロジェクトをテンプレートとして保存|현재 프로젝트를 템플릿으로 저장|Salvar o projeto atual como modelo|Сохранить текущий проект как шаблон|Geçerli projeyi şablon olarak kaydet|将当前项目另存为模板|將目前的專案另存為範本
Reusable timeline templates|Modèles de timeline réutilisables|Modelli di timeline riutilizzabili|再利用できるタイムラインテンプレート|재사용 가능한 타임라인 템플릿|Modelos de linha do tempo reutilizáveis|Шаблоны таймлайна для повторного использования|Yeniden kullanılabilir zaman çizelgesi şablonları|可重复使用的时间线模板|可重複使用的時間軸範本
Template name|Nom du modèle|Nome del modello|テンプレート名|템플릿 이름|Nome do modelo|Название шаблона|Şablon adı|模板名称|範本名稱
Import template|Importer un modèle|Importa modello|テンプレートを読み込み|템플릿 가져오기|Importar modelo|Импортировать шаблон|Şablonu içe aktar|导入模板|匯入範本
Generate and add to timeline|Générer et ajouter à la timeline|Genera e aggiungi alla timeline|生成してタイムラインに追加|생성하여 타임라인에 추가|Gerar e adicionar à linha do tempo|Создать и добавить на таймлайн|Oluştur ve zaman çizelgesine ekle|生成并添加到时间线|產生並加入時間軸
Text to speak|Texte à prononcer|Testo da pronunciare|読み上げるテキスト|읽을 텍스트|Texto para falar|Текст для озвучивания|Seslendirilecek metin|要朗读的文本|要朗讀的文字
Object cutout (U2Net small)|Détourage d'objet (U2Net small)|Scontorno oggetti (U2Net small)|物体の切り抜き（U2Net small）|개체 오려내기(U2Net small)|Recorte de objeto (U2Net small)|Вырезание объекта (U2Net small)|Nesne dekupesi (U2Net small)|物体抠像（U2Net small）|物體去背（U2Net small）
Person cutout (U2Net)|Détourage de personne (U2Net)|Scontorno persone (U2Net)|人物の切り抜き（U2Net）|인물 오려내기(U2Net)|Recorte de pessoa (U2Net)|Вырезание человека (U2Net)|Kişi dekupesi (U2Net)|人像抠像（U2Net）|人像去背（U2Net）
Kokoro local speech|Synthèse vocale locale Kokoro|Sintesi vocale locale Kokoro|Kokoro ローカル音声合成|Kokoro 로컬 음성 합성|Fala local Kokoro|Локальный синтез речи Kokoro|Kokoro yerel konuşma|Kokoro 本地语音|Kokoro 本機語音
Import Object cutout (U2Net small)|Importer le détourage d'objet (U2Net small)|Importa scontorno oggetti (U2Net small)|物体の切り抜き（U2Net small）を読み込み|개체 오려내기(U2Net small) 가져오기|Importar recorte de objeto (U2Net small)|Импортировать вырезание объекта (U2Net small)|Nesne dekupesini içe aktar (U2Net small)|导入物体抠像（U2Net small）|匯入物體去背（U2Net small）
Import Person cutout (U2Net)|Importer le détourage de personne (U2Net)|Importa scontorno persone (U2Net)|人物の切り抜き（U2Net）を読み込み|인물 오려내기(U2Net) 가져오기|Importar recorte de pessoa (U2Net)|Импортировать вырезание человека (U2Net)|Kişi dekupesini içe aktar (U2Net)|导入人像抠像（U2Net）|匯入人像去背（U2Net）
Import Kokoro local speech|Importer la synthèse vocale locale Kokoro|Importa sintesi vocale locale Kokoro|Kokoro ローカル音声合成を読み込み|Kokoro 로컬 음성 합성 가져오기|Importar fala local Kokoro|Импортировать локальный синтез речи Kokoro|Kokoro yerel konuşmayı içe aktar|导入 Kokoro 本地语音|匯入 Kokoro 本機語音
Neutral|Neutre|Neutro|ニュートラル|뉴트럴|Neutro|Нейтральный|Nötr|中性|中性
Exposure|Exposition|Esposizione|露出|노출|Exposição|Экспозиция|Pozlama|曝光|曝光
Contrast|Contraste|Contrasto|コントラスト|대비|Contraste|Контраст|Kontrast|对比度|對比
Saturation|Saturation|Saturazione|彩度|채도|Saturação|Насыщенность|Doygunluk|饱和度|飽和度
Monochrome|Monochrome|Monocromatico|モノクロ|흑백|Monocromático|Монохром|Tek renkli|单色|單色
Warmth|Chaleur|Calore|暖かみ|따뜻함|Calor|Тепло|Sıcaklık|暖调|暖調
Cooling|Refroidissement|Raffreddamento|クール|쿨링|Resfriamento|Охлаждение|Soğutma|冷调|冷調
Sepia|Sépia|Seppia|セピア|세피아|Sépia|Сепия|Sepya|棕褐色|棕褐色
Faded|Délavé|Sbiadito|色あせ|바랜 색감|Desbotado|Выцветший|Soluk|褪色|褪色
Halide Mono|Mono halogénure|Mono alogenuro|ハライドモノ|할라이드 모노|Mono haleto|Галоидный монохром|Halid mono|卤化银黑白|鹵化銀黑白
Burnished|Bruni|Brunito|バーニッシュ|번니시|Brunido|Полированный|Cilalı|抛光|拋光
Cyan Shadows|Ombres cyan|Ombre ciano|シアンのシャドウ|시안 그림자|Sombras cianas|Голубые тени|Camgöbeği gölgeler|青色阴影|青色陰影
Amber Highlights|Hautes lumières ambrées|Luci ambrate|アンバーのハイライト|앰버 하이라이트|Realces âmbar|Янтарные света|Kehribar vurgular|琥珀高光|琥珀高光
Teal Amber|Sarcelle et ambre|Verde acqua e ambra|ティールとアンバー|틸 앰버|Azul-petróleo e âmbar|Бирюза и янтарь|Deniz mavisi ve kehribar|青橙|青橙
Blush Lift|Rehaussement rosé|Tocco rosato|ブラッシュリフト|블러시 리프트|Realce rosado|Розовый подъём|Pembe dokunuş|腮红提亮|腮紅提亮
Moss Tint|Teinte mousse|Tinta muschio|モスティント|이끼 틴트|Tom musgo|Оттенок мха|Yosun tonu|苔藓色调|苔蘚色調
Nightfall|Tombée de la nuit|Crepuscolo|夕闇|해질녘|Anoitecer|Сумерки|Akşam karanlığı|夜幕|夜幕
First Light|Première lueur|Prima luce|夜明け|첫 햇살|Primeira luz|Первый свет|İlk ışık|破晓|破曉
Skip Bleach|Sans blanchiment|Salto della sbianca|銀残し|블리치 바이패스|Sem branqueamento|Пропуск отбеливания|Ağartmasız|留银|留銀
Chalk Soft|Craie douce|Gesso tenue|チョークソフト|초크 소프트|Giz suave|Мягкий мел|Yumuşak tebeşir|柔和粉笔|柔和粉筆
Hard Snap|Punch net|Contrasto deciso|ハードスナップ|하드 스냅|Contraste marcante|Жёсткий контраст|Sert vuruş|强烈对比|強烈對比
Low Key|Low key|Low key|ローキー|로우 키|Low key|Лоу-кей|Düşük ton|低调|低調
High Key|High key|High key|ハイキー|하이 키|High key|Хай-кей|Yüksek ton|高调|高調
Matte|Mat|Opaco|マット|매트|Fosco|Матовый|Mat|哑光|霧面
Jade Contrast|Contraste jade|Contrasto giada|ジェードコントラスト|제이드 대비|Contraste jade|Нефритовый контраст|Yeşim kontrast|翡翠对比|翡翠對比
Lilac Haze|Brume lilas|Foschia lilla|ライラックヘイズ|라일락 헤이즈|Névoa lilás|Сиреневая дымка|Leylak pusu|丁香薄雾|丁香薄霧
Dune Wash|Voile de dune|Velo di duna|デューンウォッシュ|듄 워시|Véu de duna|Песчаная дымка|Kum tülü|沙丘淡彩|沙丘淡彩
Glacier Bright|Glacier lumineux|Ghiacciaio luminoso|グレイシャーブライト|빙하 브라이트|Geleira brilhante|Яркий ледник|Parlak buzul|冰川亮调|冰川亮調
Harvest|Moisson|Raccolto|ハーベスト|수확|Colheita|Урожай|Hasat|丰收|豐收
Ink Shadow|Ombre d'encre|Ombra d'inchiostro|インクシャドウ|잉크 섀도|Sombra de tinta|Чернильная тень|Mürekkep gölge|墨影|墨影
Newsprint|Papier journal|Carta di giornale|新聞紙|신문지|Papel jornal|Газетная бумага|Gazete kâğıdı|报纸|報紙
Split Purple|Virage violet|Viraggio viola|スプリットパープル|스플릿 퍼플|Divisão roxa|Раздельный фиолетовый|Mor bölünmüş ton|紫色分离|紫色分離
Split Green|Virage vert|Viraggio verde|スプリットグリーン|스플릿 그린|Divisão verde|Раздельный зелёный|Yeşil bölünmüş ton|绿色分离|綠色分離
Red Lift|Rehaussement rouge|Sollevamento rosso|レッドリフト|레드 리프트|Realce vermelho|Подъём красного|Kırmızı yükseltme|红色提升|紅色提升
Blue Lift|Rehaussement bleu|Sollevamento blu|ブルーリフト|블루 리프트|Realce azul|Подъём синего|Mavi yükseltme|蓝色提升|藍色提升
Green Lift|Rehaussement vert|Sollevamento verde|グリーンリフト|그린 리프트|Realce verde|Подъём зелёного|Yeşil yükseltme|绿色提升|綠色提升
Highlight Rolloff|Atténuation des hautes lumières|Attenuazione delle luci|ハイライトロールオフ|하이라이트 롤오프|Suavização dos realces|Мягкий спад светов|Vurgu yumuşatma|高光柔化|高光柔化
Shadow Detail|Détails des ombres|Dettagli nelle ombre|シャドウディテール|그림자 디테일|Detalhes nas sombras|Детали в тенях|Gölge ayrıntısı|阴影细节|陰影細節
Vibrance|Vibrance|Vividezza|自然な彩度|생동감|Vibração|Сочность|Canlılık|自然饱和度|自然飽和度
Soft Contrast|Contraste doux|Contrasto morbido|ソフトコントラスト|부드러운 대비|Contraste suave|Мягкий контраст|Yumuşak kontrast|柔和对比|柔和對比
Crisp Mids|Tons moyens nets|Mezzitoni nitidi|クリアな中間調|선명한 중간톤|Meios-tons nítidos|Чёткие полутона|Net orta tonlar|清晰中间调|清晰中間調
Lift Blacks|Noirs relevés|Neri sollevati|黒を持ち上げる|블랙 올리기|Pretos elevados|Приподнятые чёрные|Siyahları yükselt|提亮黑色|提亮黑色
Crush Blacks|Noirs écrasés|Neri schiacciati|黒をつぶす|블랙 누르기|Pretos esmagados|Глубокие чёрные|Siyahları ez|压暗黑色|壓暗黑色
Half Stop Down|Moins un demi-diaph|Mezzo stop in meno|半段アンダー|반 스톱 낮춤|Meio stop abaixo|Минус пол-ступени|Yarım durak aşağı|降低半档|降低半檔
Desaturate|Désaturer|Desatura|彩度を下げる|채도 낮추기|Dessaturar|Обесцветить|Doygunluğu azalt|降低饱和度|降低飽和度
Brighten Mids|Éclaircir les tons moyens|Schiarisci i mezzitoni|中間調を明るく|중간톤 밝게|Clarear meios-tons|Осветлить полутона|Orta tonları aydınlat|提亮中间调|提亮中間調
Cross Process|Traitement croisé|Sviluppo incrociato|クロスプロセス|크로스 프로세스|Processo cruzado|Кросс-процесс|Çapraz işlem|交叉冲印|交叉沖印
Push Process|Développement poussé|Sviluppo tirato|増感現像|푸시 현상|Revelação puxada|Push-проявка|İtme banyosu|增感冲洗|增感沖洗
Pull Process|Développement retenu|Sviluppo ridotto|減感現像|풀 현상|Revelação reduzida|Pull-проявка|Çekme banyosu|减感冲洗|減感沖洗
Expired Stock|Pellicule périmée|Pellicola scaduta|期限切れフィルム|유통기한 지난 필름|Filme vencido|Просроченная плёнка|Süresi geçmiş film|过期胶片|過期膠片
Tintype|Ferrotype|Ferrotipo|ティンタイプ|틴타입|Ferrótipo|Ферротипия|Tenekeli baskı|锡版照相|錫版照相
Cyanotype|Cyanotype|Cianotipia|サイアノタイプ|시아노타입|Cianotipia|Цианотипия|Siyanotip|蓝晒|藍曬
Night Print|Tirage nocturne|Stampa notturna|ナイトプリント|나이트 프린트|Cópia noturna|Ночной отпечаток|Gece baskısı|夜间冲印|夜間沖印
Tungsten|Tungstène|Tungsteno|タングステン|텅스텐|Tungstênio|Вольфрам|Tungsten|钨丝灯|鎢絲燈
Candlelit|Aux chandelles|A lume di candela|キャンドルライト|촛불|À luz de velas|При свечах|Mum ışığı|烛光|燭光
Honey Glow|Lueur de miel|Bagliore di miele|ハニーグロウ|허니 글로우|Brilho de mel|Медовое сияние|Bal ışıltısı|蜂蜜光晕|蜂蜜光暈
Terracotta|Terre cuite|Terracotta|テラコッタ|테라코타|Terracota|Терракота|Terakota|陶土色|陶土色
Peach Lift|Rehaussement pêche|Tocco pesca|ピーチリフト|피치 리프트|Realce pêssego|Персиковый подъём|Şeftali dokunuş|蜜桃提亮|蜜桃提亮
Late Sun|Soleil couchant|Sole tardo|夕日|늦은 햇살|Sol da tarde|Позднее солнце|Akşam güneşi|夕阳|夕陽
Rust Shadows|Ombres rouille|Ombre ruggine|ラストシャドウ|녹빛 그림자|Sombras ferrugem|Ржавые тени|Pas rengi gölgeler|锈色阴影|鏽色陰影
Overcast|Ciel couvert|Nuvoloso|曇天|흐린 하늘|Nublado|Пасмурно|Kapalı hava|阴天|陰天
Steel Blue|Bleu acier|Blu acciaio|スチールブルー|스틸 블루|Azul-aço|Стальной синий|Çelik mavisi|钢蓝|鋼藍
Moonlit|Clair de lune|Chiaro di luna|月明かり|달빛|Luar|Лунный свет|Ay ışığı|月光|月光
Mint Air|Air mentholé|Aria di menta|ミントエア|민트 에어|Ar de menta|Мятный воздух|Nane havası|薄荷清风|薄荷清風
Deep Water|Eau profonde|Acque profonde|ディープウォーター|깊은 물|Águas profundas|Глубокая вода|Derin su|深水|深水
Frost Highlights|Hautes lumières givrées|Luci gelide|フロストハイライト|서리 하이라이트|Realces gélidos|Морозные света|Buzlu vurgular|霜冻高光|霜凍高光
Slate Shade|Ombre ardoise|Ombra ardesia|スレートシェード|슬레이트 음영|Sombra ardósia|Сланцевая тень|Arduvaz gölgesi|石板灰影|石板灰影
Red Cyan|Rouge et cyan|Rosso ciano|レッドシアン|레드 시안|Vermelho e ciano|Красный и голубой|Kırmızı camgöbeği|红青|紅青
Pine Sky|Pin et ciel|Pino e cielo|パインスカイ|소나무 하늘|Pinheiro e céu|Сосна и небо|Çam ve gök|松与天|松與天
Navy Blush|Marine et rose|Blu navy e rosa|ネイビーブラッシュ|네이비 블러시|Marinho e rosa|Тёмно-синий и розовый|Lacivert pembe|海军蓝与粉|海軍藍與粉
Violet Gold|Violet et or|Viola e oro|バイオレットゴールド|바이올렛 골드|Violeta e dourado|Фиолетовый и золотой|Mor altın|紫金|紫金
Teal Magenta|Sarcelle et magenta|Verde acqua e magenta|ティールマゼンタ|틸 마젠타|Azul-petróleo e magenta|Бирюза и пурпур|Deniz mavisi macenta|青品红|青洋紅
Cocoa Cream|Cacao et crème|Cacao e panna|ココアクリーム|코코아 크림|Cacau e creme|Какао и сливки|Kakao krema|可可奶油|可可奶油
Muted Split|Virage atténué|Viraggio tenue|ミュートスプリット|차분한 스플릿|Divisão suave|Приглушённое тонирование|Yumuşak bölünmüş ton|柔和分离色调|柔和分離色調
Gaussian Blur|Flou gaussien|Sfocatura gaussiana|ガウスぼかし|가우시안 흐림|Desfoque gaussiano|Размытие по Гауссу|Gauss bulanıklığı|高斯模糊|高斯模糊
Box Blur|Flou de zone|Sfocatura a riquadro|ボックスぼかし|박스 흐림|Desfoque de caixa|Прямоугольное размытие|Kutu bulanıklığı|方框模糊|方框模糊
Directional Blur|Flou directionnel|Sfocatura direzionale|方向ぼかし|방향 흐림|Desfoque direcional|Направленное размытие|Yönlü bulanıklık|定向模糊|定向模糊
Radial Blur|Flou radial|Sfocatura radiale|放射状ぼかし|방사형 흐림|Desfoque radial|Радиальное размытие|Dairesel bulanıklık|径向模糊|徑向模糊
Sharpen|Netteté|Nitidezza|シャープ|선명하게|Nitidez|Резкость|Keskinleştir|锐化|銳利化
Edge Detect|Détection des contours|Rilevamento bordi|エッジ検出|가장자리 감지|Detecção de bordas|Выделение краёв|Kenar algılama|边缘检测|邊緣偵測
Emboss|Estampage|Rilievo|エンボス|엠보스|Relevo|Тиснение|Kabartma|浮雕|浮雕
Invert|Inverser|Inverti|反転|반전|Inverter|Инверсия|Ters çevir|反相|負片
Posterize|Postérisation|Posterizzazione|ポスタリゼーション|포스터화|Posterizar|Постеризация|Posterleştir|色调分离|色調分離
Solarize|Solarisation|Solarizzazione|ソラリゼーション|솔라리제이션|Solarizar|Соляризация|Solarize|曝光过度|曝光過度
Pixelate|Pixelisation|Pixelizzazione|モザイク|픽셀화|Pixelizar|Пикселизация|Pikselleştir|像素化|像素化
Vignette|Vignettage|Vignettatura|周辺減光|비네트|Vinheta|Виньетка|Vinyet|暗角|暈影
Film Grain|Grain de film|Grana della pellicola|フィルムグレイン|필름 그레인|Granulação de filme|Плёночное зерно|Film grenli|胶片颗粒|膠片顆粒
Glow|Lueur|Bagliore|グロー|글로우|Brilho|Свечение|Parlama|辉光|光暈
Chromatic Aberration|Aberration chromatique|Aberrazione cromatica|色収差|색수차|Aberração cromática|Хроматическая аберрация|Renk sapması|色差|色差
Fisheye|Fisheye|Fisheye|魚眼|어안|Olho de peixe|Рыбий глаз|Balıkgözü|鱼眼|魚眼
Wave|Vague|Onda|波形|물결|Onda|Волна|Dalga|波浪|波浪
Mirror|Miroir|Specchio|ミラー|미러|Espelho|Зеркало|Ayna|镜像|鏡像
Kaleidoscope|Kaléidoscope|Caleidoscopio|万華鏡|만화경|Caleidoscópio|Калейдоскоп|Kaleydoskop|万花筒|萬花筒
Scanlines|Lignes de balayage|Linee di scansione|走査線|스캔라인|Linhas de varredura|Строки развёртки|Tarama çizgileri|扫描线|掃描線
Signal Interference|Interférences|Interferenza di segnale|信号干渉|신호 간섭|Interferência de sinal|Помехи сигнала|Sinyal paraziti|信号干扰|訊號干擾
Cartoon|Dessin animé|Cartone|カートゥーン|카툰|Desenho animado|Мультфильм|Çizgi film|卡通|卡通
Pencil Sketch|Croquis au crayon|Schizzo a matita|鉛筆スケッチ|연필 스케치|Esboço a lápis|Карандашный набросок|Kurşun kalem eskiz|铅笔素描|鉛筆素描
Rain|Pluie|Pioggia|雨|비|Chuva|Дождь|Yağmur|雨|雨
Dust|Poussière|Polvere|ほこり|먼지|Poeira|Пыль|Toz|灰尘|灰塵
Camera Shake|Tremblement de caméra|Tremolio della camera|手ぶれ|카메라 흔들림|Tremor de câmera|Дрожание камеры|Kamera sarsıntısı|镜头晃动|鏡頭晃動
Tilt Shift|Tilt-shift|Tilt-shift|ティルトシフト|틸트 시프트|Tilt-shift|Тилт-шифт|Tilt-shift|移轴|移軸
Spin Blur|Flou tournoyant|Sfocatura rotatoria|回転ぼかし|회전 흐림|Desfoque giratório|Размытие вращением|Dönme bulanıklığı|旋转模糊|旋轉模糊
Lens Blur|Flou d'objectif|Sfocatura obiettivo|レンズぼかし|렌즈 흐림|Desfoque de lente|Размытие объектива|Lens bulanıklığı|镜头模糊|鏡頭模糊
Median Soften|Adoucissement médian|Ammorbidimento mediano|メディアンで柔らかく|중앙값 부드럽게|Suavização mediana|Медианное смягчение|Medyan yumuşatma|中值柔化|中值柔化
Soft Focus|Flou artistique|Fuoco morbido|ソフトフォーカス|소프트 포커스|Foco suave|Мягкий фокус|Yumuşak odak|柔焦|柔焦
Diagonal Blur|Flou diagonal|Sfocatura diagonale|斜めぼかし|대각선 흐림|Desfoque diagonal|Диагональное размытие|Çapraz bulanıklık|对角模糊|對角模糊
Ghost Trail|Traînée fantôme|Scia fantasma|ゴーストトレイル|잔상|Rastro fantasma|Призрачный шлейф|Hayalet iz|残影拖尾|殘影拖尾
Halftone|Similigravure|Mezzetinte|ハーフトーン|하프톤|Meio-tom|Полутон|Yarım ton|半色调|半色調
Duotone|Bichromie|Bicromia|デュオトーン|듀오톤|Duotone|Дуотон|Çift ton|双色调|雙色調
Paint Wash|Lavis|Acquerellato|ペイントウォッシュ|페인트 워시|Aguada|Живописная размывка|Boya yıkama|水彩晕染|水彩暈染
Thermal|Thermique|Termico|サーマル|열화상|Térmico|Тепловизор|Termal|热成像|熱成像
Night Vision|Vision nocturne|Visione notturna|暗視|야간 투시|Visão noturna|Ночное видение|Gece görüşü|夜视|夜視
Ink Outline|Contour à l'encre|Contorno a inchiostro|インクアウトライン|잉크 윤곽선|Contorno a tinta|Чернильный контур|Mürekkep hattı|墨水描边|墨水描邊
Crosshatch|Hachures croisées|Tratteggio incrociato|クロスハッチ|크로스해치|Hachura cruzada|Перекрёстная штриховка|Çapraz tarama|交叉排线|交叉排線
Swirl|Tourbillon|Vortice|渦巻き|소용돌이|Redemoinho|Завихрение|Girdap|漩涡|漩渦
Ripple|Ondulation|Increspatura|波紋|잔물결|Ondulação|Рябь|Dalgacık|涟漪|漣漪
Pinch|Pincement|Pizzico|ピンチ|오목|Pinçar|Сжатие|Sıkıştırma|收缩|收縮
Slice Glitch|Glitch en tranches|Glitch a fette|スライスグリッチ|슬라이스 글리치|Glitch em fatias|Глитч срезами|Dilim bozulması|切片故障|切片故障
Tile Repeat|Répétition en mosaïque|Ripetizione a tessere|タイル繰り返し|타일 반복|Repetição em ladrilhos|Повтор плиткой|Döşeme tekrarı|平铺重复|平鋪重複
Polar Wrap|Enroulement polaire|Avvolgimento polare|極座標ラップ|극좌표 감싸기|Envolvimento polar|Полярное обёртывание|Kutupsal sarma|极坐标环绕|極座標環繞
Heat Haze|Brume de chaleur|Foschia di calore|陽炎|아지랑이|Névoa de calor|Марево|Sıcak pus|热浪扭曲|熱浪扭曲
Film Scratches|Rayures de film|Graffi della pellicola|フィルムの傷|필름 스크래치|Arranhões de filme|Царапины плёнки|Film çizikleri|胶片划痕|膠片刮痕
Light Leak|Fuite de lumière|Infiltrazione di luce|光漏れ|빛 번짐|Vazamento de luz|Засветка|Işık sızıntısı|漏光|漏光
Aperture Grille|Grille d'ouverture|Griglia di apertura|アパーチャーグリル|애퍼처 그릴|Grade de abertura|Апертурная решётка|Açıklık ızgarası|荫栅|蔭柵
Paper Texture|Texture papier|Texture carta|紙のテクスチャ|종이 질감|Textura de papel|Текстура бумаги|Kâğıt dokusu|纸张纹理|紙張紋理
Snowfall|Chute de neige|Nevicata|降雪|눈 내림|Queda de neve|Снегопад|Kar yağışı|降雪|降雪
Bokeh Spots|Taches de bokeh|Punti bokeh|ボケの玉|보케 점|Pontos de bokeh|Пятна боке|Bokeh noktaları|散景光斑|散景光斑
Chroma Noise|Bruit chromatique|Rumore cromatico|カラーノイズ|색상 노이즈|Ruído cromático|Цветовой шум|Renk gürültüsü|色度噪点|色度雜訊
Pitch Up|Hauteur plus aiguë|Tono più alto|ピッチアップ|피치 올리기|Tom acima|Выше тон|Perdeyi yükselt|升调|升調
Pitch Down|Hauteur plus grave|Tono più basso|ピッチダウン|피치 내리기|Tom abaixo|Ниже тон|Perdeyi düşür|降调|降調
Denoise|Débruitage|Riduzione rumore|ノイズ除去|노이즈 제거|Remover ruído|Шумоподавление|Gürültü giderme|降噪|降噪
Voice Clean|Voix nette|Voce pulita|ボイスクリーン|음성 정리|Voz limpa|Чистый голос|Ses temizleme|人声净化|人聲淨化
Bass|Graves|Bassi|低音|저음|Graves|Бас|Bas|低音|低音
Treble|Aigus|Alti|高音|고음|Agudos|Высокие|Tiz|高音|高音
Telephone|Téléphone|Telefono|電話|전화|Telefone|Телефон|Telefon|电话|電話
Room|Pièce|Stanza|ルーム|룸|Sala|Комната|Oda|房间|房間
Hall|Salle|Sala|ホール|홀|Salão|Зал|Salon|大厅|大廳
Cathedral|Cathédrale|Cattedrale|大聖堂|대성당|Catedral|Собор|Katedral|大教堂|大教堂
Plate|Plaque|Piastra|プレート|플레이트|Placa|Пластина|Plaka|板式|板式
Robot|Robot|Robot|ロボット|로봇|Robô|Робот|Robot|机器人|機器人
Tremolo|Trémolo|Tremolo|トレモロ|트레몰로|Tremolo|Тремоло|Tremolo|颤音|顫音
Vibrato|Vibrato|Vibrato|ビブラート|비브라토|Vibrato|Вибрато|Vibrato|揉音|揉音
Distortion|Distorsion|Distorsione|ディストーション|디스토션|Distorção|Дисторшн|Distorsiyon|失真|失真
Compress|Compression|Compressione|コンプレッサー|컴프레서|Compressão|Компрессия|Sıkıştırma|压缩|壓縮
Normalize|Normaliser|Normalizza|ノーマライズ|노멀라이즈|Normalizar|Нормализация|Normalleştir|标准化|正規化
De-ess|De-esser|De-esser|ディエッサー|디에서|De-esser|Де-эссер|De-esser|齿音消除|齒音消除
Octave Up|Octave au-dessus|Ottava sopra|オクターブ上|옥타브 위|Oitava acima|Октава вверх|Oktav yukarı|升八度|升八度
Octave Down|Octave en dessous|Ottava sotto|オクターブ下|옥타브 아래|Oitava abaixo|Октава вниз|Oktav aşağı|降八度|降八度
Double Voice|Voix doublée|Voce raddoppiata|ダブルボイス|더블 보이스|Voz dobrada|Двойной голос|Çift ses|双重人声|雙重人聲
Jet Flange|Flanger jet|Flanger jet|ジェットフランジャー|제트 플랜저|Flanger jato|Реактивный флэнджер|Jet flanger|喷气镶边|噴射鑲邊
Swirl Phase|Phaser tourbillonnant|Phaser vorticoso|スワールフェイザー|스월 페이저|Phaser rodopiante|Кружащий фэйзер|Girdap faz|漩涡相位|漩渦相位
Bullhorn|Mégaphone|Megafono|拡声器|확성기|Megafone|Мегафон|Megafon|扩音器|擴音器
Two Way Radio|Talkie-walkie|Ricetrasmittente|トランシーバー|무전기|Rádio comunicador|Рация|Telsiz|对讲机|對講機
Warm Lows|Graves chauds|Bassi caldi|温かい低域|따뜻한 저음|Graves quentes|Тёплые низы|Sıcak baslar|温暖低频|溫暖低頻
Presence Lift|Présence rehaussée|Presenza accentuata|プレゼンス強調|프레즌스 강조|Realce de presença|Подъём присутствия|Varlık artırma|临场感提升|臨場感提升
Mid Scoop|Creux dans les médiums|Scavo delle medie|中域カット|중음 감소|Corte de médios|Провал середины|Orta frekans oyma|中频凹陷|中頻凹陷
Bit Crush|Bitcrusher|Bitcrusher|ビットクラッシュ|비트 크러시|Bitcrusher|Биткрашер|Bit ezme|比特破碎|位元破碎
Tape Warmth|Chaleur de bande|Calore del nastro|テープの温かみ|테이프 온기|Calor de fita|Тепло ленты|Bant sıcaklığı|磁带暖声|磁帶暖聲
Crisp Detail|Détail net|Dettaglio nitido|クリアなディテール|선명한 디테일|Detalhe nítido|Чёткая детализация|Net ayrıntı|清脆细节|清脆細節
Lofi Band|Bande lo-fi|Banda lo-fi|ローファイバンド|로파이 밴드|Faixa lo-fi|Лоу-фай полоса|Lo-fi bant|低保真频段|低傳真頻段
Slapback|Slapback|Slapback|スラップバック|슬랩백|Slapback|Слэпбэк|Slapback|拍击回声|拍擊回聲
Wide Stage|Scène large|Palco ampio|ワイドステージ|넓은 무대|Palco amplo|Широкая сцена|Geniş sahne|宽舞台|寬舞台
Stereo Bloom|Épanouissement stéréo|Apertura stereo|ステレオブルーム|스테레오 블룸|Expansão estéreo|Стерео-расширение|Stereo açılım|立体声扩展|立體聲擴展
Long Tail|Longue traîne|Coda lunga|ロングテール|긴 잔향|Cauda longa|Длинный хвост|Uzun kuyruk|长尾|長尾
Tunnel|Tunnel|Tunnel|トンネル|터널|Túnel|Туннель|Tünel|隧道|隧道
Small Booth|Petite cabine|Cabina piccola|小さなブース|작은 부스|Cabine pequena|Маленькая кабина|Küçük kabin|小隔间|小隔間
Far Away|Au loin|Lontano|遠くから|먼 곳|Distante|Вдалеке|Uzakta|远处|遠處
Noise Gate|Noise gate|Noise gate|ノイズゲート|노이즈 게이트|Noise gate|Нойз-гейт|Gürültü kapısı|噪声门|噪音閘門
Hiss Cut|Suppression du souffle|Taglio del fruscio|ヒスカット|히스 제거|Corte de chiado|Удаление шипения|Tıslama kesme|嘶声消除|嘶聲消除
Hum Remover|Suppression du ronflement|Rimozione del ronzio|ハム除去|험 제거|Remoção de zumbido|Удаление гула|Uğultu giderici|嗡声消除|嗡聲消除
Rumble Cut|Coupe-grondement|Taglio del rombo|ランブルカット|럼블 제거|Corte de ronco|Удаление рокота|Gürleme kesme|隆隆声消除|隆隆聲消除
Level Rider|Régulateur de niveau|Livellatore|レベルライダー|레벨 라이더|Controle de nível|Выравниватель уровня|Seviye dengeleyici|电平追踪|電平追蹤
Peak Limiter|Limiteur de crêtes|Limitatore di picco|ピークリミッター|피크 리미터|Limitador de pico|Пиковый лимитер|Tepe sınırlayıcı|峰值限制器|峰值限制器
Deep Denoise|Débruitage profond|Riduzione rumore profonda|ディープノイズ除去|강력 노이즈 제거|Remoção profunda de ruído|Глубокое шумоподавление|Derin gürültü giderme|深度降噪|深度降噪
Wipe Left|Balayage vers la gauche|Tendina a sinistra|左へワイプ|왼쪽으로 닦아내기|Revelar para a esquerda|Шторка влево|Sola silme|向左擦除|向左擦除
Wipe Right|Balayage vers la droite|Tendina a destra|右へワイプ|오른쪽으로 닦아내기|Revelar para a direita|Шторка вправо|Sağa silme|向右擦除|向右擦除
Wipe Up|Balayage vers le haut|Tendina verso l'alto|上へワイプ|위로 닦아내기|Revelar para cima|Шторка вверх|Yukarı silme|向上擦除|向上擦除
Wipe Down|Balayage vers le bas|Tendina verso il basso|下へワイプ|아래로 닦아내기|Revelar para baixo|Шторка вниз|Aşağı silme|向下擦除|向下擦除
Slide Left|Glissement vers la gauche|Scorrimento a sinistra|左へスライド|왼쪽으로 밀기|Deslizar para a esquerda|Сдвиг влево|Sola kaydır|向左滑动|向左滑動
Slide Right|Glissement vers la droite|Scorrimento a destra|右へスライド|오른쪽으로 밀기|Deslizar para a direita|Сдвиг вправо|Sağa kaydır|向右滑动|向右滑動
Zoom|Zoom|Zoom|ズーム|줌|Zoom|Масштаб|Yakınlaştırma|缩放|縮放
Iris|Iris|Iride|アイリス|아이리스|Íris|Диафрагма|İris|光圈|光圈
Dissolve|Fondu|Dissolvenza|ディゾルブ|디졸브|Dissolver|Растворение|Çözülme|溶解|溶解
Push Up|Poussée vers le haut|Spinta verso l'alto|上へプッシュ|위로 밀어내기|Empurrar para cima|Выталкивание вверх|Yukarı it|向上推|向上推
Normal|Normal|Normale|通常|표준|Normal|Обычный|Normal|正常|正常
Multiply|Produit|Moltiplica|乗算|곱하기|Multiplicação|Умножение|Çarp|正片叠底|色彩增值
Screen|Superposition|Scolora|スクリーン|스크린|Tela|Экран|Ekran|滤色|濾色
Overlay|Incrustation|Sovrapponi|オーバーレイ|오버레이|Sobrepor|Перекрытие|Bindirme|叠加|覆蓋
Darken|Obscurcir|Scurisci|比較（暗）|어둡게 하기|Escurecer|Затемнение|Koyulaştır|变暗|變暗
Lighten|Éclaircir|Schiarisci|比較（明）|밝게 하기|Clarear|Замена светлым|Açıklaştır|变亮|變亮
Difference|Différence|Differenza|差の絶対値|차이|Diferença|Разница|Fark|差值|差異化
Add|Addition|Aggiungi|加算|더하기|Adição|Сложение|Ekle|相加|增加
Subtract|Soustraction|Sottrai|減算|빼기|Subtração|Вычитание|Çıkar|减去|減去
Soft Light|Lumière tamisée|Luce soffusa|ソフトライト|소프트 라이트|Luz suave|Мягкий свет|Yumuşak ışık|柔光|柔光
media|médias|media|メディア|미디어|mídia|медиа|medya|媒体|媒體
effect previews|aperçus d'effets|anteprime degli effetti|エフェクトのプレビュー|효과 미리보기|prévias de efeitos|превью эффектов|efekt önizlemeleri|效果预览|效果預覽
filmstrips|pellicules|filmstrip|フィルムストリップ|필름스트립|tiras de filme|раскадровки|film şeritleri|胶片条|膠片條
waveforms|formes d'onde|forme d'onda|波形|파형|formas de onda|волновые формы|dalga biçimleri|波形|波形
thumbnails|vignettes|miniature|サムネイル|썸네일|miniaturas|миниатюры|küçük resimler|缩略图|縮圖
Uniform|Uniforme|Uniforme|一定|균일|Uniforme|Равномерно|Düzgün|匀速|等速
Accelerate|Accélérer|Accelera|加速|가속|Acelerar|Ускорение|Hızlan|加速|加速
Decelerate|Ralentir|Decelera|減速|감속|Desacelerar|Замедление|Yavaşla|减速|減速
Valley|Creux|Valle|谷|골짜기|Vale|Впадина|Vadi|低谷|低谷
Peak|Pic|Picco|山|정점|Pico|Пик|Tepe|高峰|高峰
Pulse|Pulsation|Pulsazione|パルス|펄스|Pulso|Пульс|Nabız|脉冲|脈衝
Slide left|Glisser à gauche|Scorri a sinistra|左へスライド|왼쪽으로 슬라이드|Deslizar para a esquerda|Сдвиг влево|Sola kaydır|向左滑入|向左滑入
Slide right|Glisser à droite|Scorri a destra|右へスライド|오른쪽으로 슬라이드|Deslizar para a direita|Сдвиг вправо|Sağa kaydır|向右滑入|向右滑入
Slide up|Glisser vers le haut|Scorri verso l'alto|上へスライド|위로 슬라이드|Deslizar para cima|Сдвиг вверх|Yukarı kaydır|向上滑入|向上滑入
Slide down|Glisser vers le bas|Scorri verso il basso|下へスライド|아래로 슬라이드|Deslizar para baixo|Сдвиг вниз|Aşağı kaydır|向下滑入|向下滑入
Spin in|Entrée en rotation|Entrata rotante|回転イン|회전하며 등장|Entrada girando|Появление с вращением|Dönerek giriş|旋转进入|旋轉進入
Float|Flottement|Fluttuazione|浮遊|떠다니기|Flutuar|Парение|Süzülme|漂浮|漂浮
Shake|Secousse|Scossa|シェイク|흔들기|Tremer|Тряска|Sarsıntı|抖动|抖動
Ripple delete on selected track|Suppression avec décalage sur la piste sélectionnée|Elimina con riallineamento sulla traccia selezionata|選択トラックでリップル削除|선택한 트랙에서 리플 삭제|Excluir com ondulação na trilha selecionada|Удалить со сдвигом на выбранной дорожке|Seçili parçada kaydırarak sil|在所选轨道上波纹删除|在所選軌道上漣漪刪除
Add track|Ajouter une piste|Aggiungi traccia|トラックを追加|트랙 추가|Adicionar trilha|Добавить дорожку|Parça ekle|添加轨道|新增軌道
Fit timeline|Ajuster la timeline|Adatta timeline|タイムラインに合わせる|타임라인 맞춤|Ajustar linha do tempo|Вместить таймлайн|Zaman çizelgesini sığdır|适应时间线|符合時間軸
Zoom out|Zoom arrière|Riduci zoom|ズームアウト|축소|Reduzir zoom|Уменьшить|Uzaklaştır|缩小|縮小
Zoom in|Zoom avant|Aumenta zoom|ズームイン|확대|Ampliar zoom|Увеличить|Yakınlaştır|放大|放大
Search effects and filters|Rechercher effets et filtres|Cerca effetti e filtri|エフェクトとフィルターを検索|효과 및 필터 검색|Pesquisar efeitos e filtros|Поиск эффектов и фильтров|Efekt ve filtre ara|搜索效果和滤镜|搜尋效果與濾鏡
Select a clip on the timeline to edit its properties|Sélectionnez un clip dans la timeline pour modifier ses propriétés|Seleziona una clip nella timeline per modificarne le proprietà|プロパティを編集するにはタイムラインでクリップを選択してください|속성을 편집할 클립을 타임라인에서 선택하세요|Selecione um clipe na linha do tempo para editar suas propriedades|Выберите клип на таймлайне, чтобы изменить его свойства|Özelliklerini düzenlemek için zaman çizelgesinden bir klip seçin|在时间线上选择片段以编辑其属性|在時間軸上選擇片段以編輯其屬性
Reset transform|Réinitialiser la transformation|Reimposta trasformazione|変形をリセット|변형 초기화|Redefinir transformação|Сбросить преобразование|Dönüşümü sıfırla|重置变换|重設變形
Show all properties|Afficher toutes les propriétés|Mostra tutte le proprietà|すべてのプロパティを表示|모든 속성 표시|Mostrar todas as propriedades|Показать все свойства|Tüm özellikleri göster|显示所有属性|顯示所有屬性
Previous keyframe|Image clé précédente|Fotogramma chiave precedente|前のキーフレーム|이전 키프레임|Quadro-chave anterior|Предыдущий ключевой кадр|Önceki anahtar kare|上一个关键帧|上一個關鍵影格
Next keyframe|Image clé suivante|Fotogramma chiave successivo|次のキーフレーム|다음 키프레임|Próximo quadro-chave|Следующий ключевой кадр|Sonraki anahtar kare|下一个关键帧|下一個關鍵影格
Keyframe at playhead|Image clé à la tête de lecture|Fotogramma chiave sulla testina|再生ヘッドにキーフレーム|재생 헤드에 키프레임|Quadro-chave no cursor|Ключевой кадр на курсоре|Oynatma kafasında anahtar kare|在播放头处添加关键帧|在播放磁頭處加入關鍵影格
Preparing demo|Préparation de la démo|Preparazione della demo|デモを準備中|데모 준비 중|Preparando a demonstração|Подготовка демо|Demo hazırlanıyor|正在准备示例|正在準備示範
Card size|Taille des vignettes|Dimensione schede|カードサイズ|카드 크기|Tamanho dos cartões|Размер карточек|Kart boyutu|卡片大小|卡片大小
Rectangle mask|Masque rectangulaire|Maschera rettangolare|長方形マスク|사각형 마스크|Máscara retangular|Прямоугольная маска|Dikdörtgen maske|矩形蒙版|矩形遮罩
Ellipse mask|Masque elliptique|Maschera ellittica|楕円マスク|타원 마스크|Máscara elíptica|Эллиптическая маска|Elips maske|椭圆蒙版|橢圓遮罩
Object cutout|Découpe d'objet|Scontorno oggetto|オブジェクト切り抜き|개체 오려내기|Recorte de objeto|Вырезание объекта|Nesne kesme|物体抠像|物件去背
Person cutout|Découpe de personne|Scontorno persona|人物切り抜き|인물 오려내기|Recorte de pessoa|Вырезание человека|Kişi kesme|人物抠像|人物去背
Speak|Synthèse vocale|Voce sintetica|読み上げ|음성 생성|Narração|Озвучка|Konuşma|配音|配音
Detach audio|Détacher l'audio|Separa audio|音声を分離|오디오 분리|Separar áudio|Отделить звук|Sesi ayır|分离音频|分離音訊
Select a clip on the timeline first|Sélectionnez d'abord un clip dans la timeline|Seleziona prima una clip nella timeline|まずタイムラインでクリップを選択してください|먼저 타임라인에서 클립을 선택하세요|Primeiro selecione um clipe na linha do tempo|Сначала выберите клип на таймлайне|Önce zaman çizelgesinden bir klip seçin|请先在时间线上选择片段|請先在時間軸上選擇片段
Added|Ajouté|Aggiunto|追加|추가됨|Adicionado|Добавлено|Eklendi|已添加|已新增
Removed|Retiré|Rimosso|削除|제거됨|Removido|Удалено|Kaldırıldı|已移除|已移除
This effect needs a clip with sound|Cet effet nécessite un clip avec du son|Questo effetto richiede una clip con audio|このエフェクトには音声のあるクリップが必要です|이 효과에는 소리가 있는 클립이 필요합니다|Este efeito precisa de um clipe com som|Этому эффекту нужен клип со звуком|Bu efekt sesli bir klip gerektirir|此效果需要带声音的片段|此效果需要有聲音的片段
Mask added, adjust it in the inspector|Masque ajouté, ajustez-le dans l'inspecteur|Maschera aggiunta, regolala nell'ispettore|マスクを追加しました。インスペクターで調整してください|마스크를 추가했습니다. 인스펙터에서 조정하세요|Máscara adicionada, ajuste-a no inspetor|Маска добавлена, настройте её в инспекторе|Maske eklendi, denetçiden ayarlayın|已添加蒙版，请在检查器中调整|已新增遮罩，請在檢視器中調整
Cutout needs a video or image clip|La découpe nécessite un clip vidéo ou image|Lo scontorno richiede una clip video o immagine|切り抜きには動画または画像クリップが必要です|오려내기에는 비디오 또는 이미지 클립이 필요합니다|O recorte precisa de um clipe de vídeo ou imagem|Для вырезания нужен видео- или фотоклип|Kesme için video veya görsel klip gerekir|抠像需要视频或图像片段|去背需要影片或影像片段
Install the model in Studio, Local models|Installez le modèle dans Studio, Modèles locaux|Installa il modello in Studio, Modelli locali|スタジオの「ローカルモデル」でモデルをインストールしてください|스튜디오의 로컬 모델에서 모델을 설치하세요|Instale o modelo em Estúdio, Modelos locais|Установите модель в разделе Студия, Локальные модели|Modeli Stüdyo, Yerel modeller bölümünden yükleyin|请在工作室的本地模型中安装模型|請在工作室的本機模型中安裝模型
Could not apply this effect|Impossible d'appliquer cet effet|Impossibile applicare questo effetto|このエフェクトを適用できませんでした|이 효과를 적용할 수 없습니다|Não foi possível aplicar este efeito|Не удалось применить этот эффект|Bu efekt uygulanamadı|无法应用此效果|無法套用此效果
Effects are unavailable until the engine responds|Les effets sont indisponibles jusqu'à la réponse du moteur|Gli effetti non sono disponibili finché il motore non risponde|エンジンが応答するまでエフェクトは利用できません|엔진이 응답할 때까지 효과를 사용할 수 없습니다|Os efeitos ficam indisponíveis até o motor responder|Эффекты недоступны, пока движок не ответит|Motor yanıt verene kadar efektler kullanılamaz|引擎响应前无法使用效果|引擎回應前無法使用效果
Download Kokoro under Local models first|Téléchargez d'abord Kokoro dans Modèles locaux|Scarica prima Kokoro in Modelli locali|まず「ローカルモデル」で Kokoro をダウンロードしてください|먼저 로컬 모델에서 Kokoro를 다운로드하세요|Baixe o Kokoro em Modelos locais primeiro|Сначала загрузите Kokoro в разделе Локальные модели|Önce Yerel modeller bölümünden Kokoro'yu indirin|请先在本地模型中下载 Kokoro|請先在本機模型中下載 Kokoro
System default|Par défaut du système|Predefinito di sistema|システムの既定|시스템 기본값|Padrão do sistema|Системный по умолчанию|Sistem varsayılanı|系统默认|系統預設
Animated property|Propriété animée|Proprietà animata|アニメーションするプロパティ|애니메이션 속성|Propriedade animada|Анимируемое свойство|Canlandırılan özellik|动画属性|動畫屬性
Apply expression|Appliquer l'expression|Applica espressione|式を適用|표현식 적용|Aplicar expressão|Применить выражение|İfadeyi uygula|应用表达式|套用運算式
Remove LUT|Retirer la LUT|Rimuovi LUT|LUT を削除|LUT 제거|Remover LUT|Удалить LUT|LUT'u kaldır|移除 LUT|移除 LUT
Remove shader|Retirer le shader|Rimuovi shader|シェーダーを削除|셰이더 제거|Remover shader|Удалить шейдер|Gölgelendiriciyi kaldır|移除着色器|移除著色器
Transition|Transition|Transizione|トランジション|전환|Transição|Переход|Geçiş|转场|轉場
WGSL shader|Shader WGSL|Shader WGSL|WGSL シェーダー|WGSL 셰이더|Shader WGSL|Шейдер WGSL|WGSL gölgelendirici|WGSL 着色器|WGSL 著色器
Also run setup_local_ai to install the speech runtime|Exécutez aussi setup_local_ai pour installer le moteur vocal|Esegui anche setup_local_ai per installare il motore vocale|音声ランタイムをインストールするため setup_local_ai も実行してください|음성 런타임을 설치하려면 setup_local_ai도 실행하세요|Execute também setup_local_ai para instalar o motor de voz|Также запустите setup_local_ai, чтобы установить речевой движок|Konuşma çalışma zamanını kurmak için setup_local_ai dosyasını da çalıştırın|还需运行 setup_local_ai 安装语音运行时|還需執行 setup_local_ai 安裝語音執行環境
Model ready|Modèle prêt|Modello pronto|モデルの準備ができました|모델 준비 완료|Modelo pronto|Модель готова|Model hazır|模型已就绪|模型已就緒
Model files ready. Speech also needs setup_local_ai|Fichiers du modèle prêts. La voix nécessite aussi setup_local_ai|File del modello pronti. La voce richiede anche setup_local_ai|モデルファイルの準備完了。音声には setup_local_ai も必要です|모델 파일 준비 완료. 음성에는 setup_local_ai도 필요합니다|Arquivos do modelo prontos. A voz também precisa de setup_local_ai|Файлы модели готовы. Для речи также нужен setup_local_ai|Model dosyaları hazır. Konuşma için setup_local_ai de gerekir|模型文件已就绪。语音还需 setup_local_ai|模型檔案已就緒。語音還需 setup_local_ai
Needs setup_local_ai for its runtime|Nécessite setup_local_ai pour son moteur|Richiede setup_local_ai per il suo motore|ランタイムに setup_local_ai が必要です|런타임에 setup_local_ai가 필요합니다|Precisa de setup_local_ai para seu motor|Требует setup_local_ai для своей среды|Çalışma zamanı için setup_local_ai gerekir|其运行时需要 setup_local_ai|其執行環境需要 setup_local_ai
Decoding audio|Décodage de l'audio|Decodifica dell'audio|音声をデコード中|오디오 디코딩 중|Decodificando áudio|Декодирование звука|Ses çözümleniyor|正在解码音频|正在解碼音訊
Could not decode audio from this media|Impossible de décoder l'audio de ce média|Impossibile decodificare l'audio di questo media|このメディアの音声をデコードできませんでした|이 미디어의 오디오를 디코딩할 수 없습니다|Não foi possível decodificar o áudio desta mídia|Не удалось декодировать звук этого файла|Bu medyanın sesi çözümlenemedi|无法解码此媒体的音频|無法解碼此媒體的音訊
No speech found|Aucune parole détectée|Nessun parlato rilevato|音声が検出されませんでした|음성을 찾지 못했습니다|Nenhuma fala encontrada|Речь не найдена|Konuşma bulunamadı|未检测到语音|未偵測到語音
Captions added|Sous-titres ajoutés|Sottotitoli aggiunti|字幕を追加しました|자막을 추가했습니다|Legendas adicionadas|Субтитры добавлены|Altyazılar eklendi|已添加字幕|已新增字幕
Captions added to a new track|Sous-titres ajoutés sur une nouvelle piste|Sottotitoli aggiunti su una nuova traccia|新しいトラックに字幕を追加しました|새 트랙에 자막을 추가했습니다|Legendas adicionadas em uma nova trilha|Субтитры добавлены на новую дорожку|Altyazılar yeni bir parçaya eklendi|已在新轨道添加字幕|已在新軌道新增字幕
Transcription failed|La transcription a échoué|Trascrizione non riuscita|文字起こしに失敗しました|전사에 실패했습니다|A transcrição falhou|Транскрипция не удалась|Transkripsiyon başarısız oldu|转写失败|轉寫失敗
Text|Texte|Testo|テキスト|텍스트|Texto|Текст|Metin|文字|文字
Transitions|Transitions|Transizioni|トランジション|전환|Transições|Переходы|Geçişler|转场|轉場
Effects|Effets|Effetti|エフェクト|효과|Efeitos|Эффекты|Efektler|效果|效果
Stock|Banque de médias|Archivio multimediale|素材ライブラリ|스톡 미디어|Banco de mídia|Медиатека|Stok medya|素材库|素材庫
Import|Importer|Importa|読み込み|가져오기|Importar|Импорт|İçe aktar|导入|匯入
File|Fichier|File|ファイル|파일|Arquivo|Файл|Dosya|文件|檔案
Edit|Édition|Modifica|編集|편집|Editar|Правка|Düzenle|编辑|編輯
View|Affichage|Vista|表示|보기|Exibir|Вид|Görünüm|视图|檢視
Export|Exporter|Esporta|書き出し|내보내기|Exportar|Экспорт|Dışa aktar|导出|匯出
New project|Nouveau projet|Nuovo progetto|新規プロジェクト|새 프로젝트|Novo projeto|Новый проект|Yeni proje|新建项目|新增專案
Save project|Enregistrer le projet|Salva progetto|プロジェクトを保存|프로젝트 저장|Salvar projeto|Сохранить проект|Projeyi kaydet|保存项目|儲存專案
Demo project|Projet de démonstration|Progetto dimostrativo|デモプロジェクト|데모 프로젝트|Projeto de demonstração|Демопроект|Örnek proje|示例项目|示範專案
Recent projects|Projets récents|Progetti recenti|最近のプロジェクト|최근 프로젝트|Projetos recentes|Недавние проекты|Son projeler|最近项目|最近專案
Language|Langue|Lingua|言語|언어|Idioma|Язык|Dil|语言|語言
Transform|Transformation|Trasformazione|変形|변형|Transformação|Преобразование|Dönüştür|变换|變形
Timing|Durée et vitesse|Tempi e velocità|時間と速度|시간 및 속도|Tempo e velocidade|Время и скорость|Zamanlama|时间与速度|時間與速度
Blend|Fusion|Fusione|合成|혼합|Mesclagem|Смешивание|Karıştırma|混合|混合
Key|Incrustation|Chroma key|クロマキー|크로마 키|Chroma key|Хромакей|Renk anahtarı|抠像|色鍵
Scale|Échelle|Scala|拡大率|크기|Escala|Масштаб|Ölçek|缩放|縮放
Position X|Position X|Posizione X|X位置|X 위치|Posição X|Позиция X|X konumu|X 位置|X 位置
Position Y|Position Y|Posizione Y|Y位置|Y 위치|Posição Y|Позиция Y|Y konumu|Y 位置|Y 位置
Rotation|Rotation|Rotazione|回転|회전|Rotação|Поворот|Döndürme|旋转|旋轉
Width|Largeur|Larghezza|幅|너비|Largura|Ширина|Genişlik|宽度|寬度
Height|Hauteur|Altezza|高さ|높이|Altura|Высота|Yükseklik|高度|高度
Opacity|Opacité|Opacità|不透明度|불투명도|Opacidade|Непрозрачность|Opaklık|不透明度|不透明度
Mode|Mode|Modalità|モード|모드|Modo|Режим|Mod|模式|模式
Flip horizontal|Retourner horizontalement|Rifletti orizzontalmente|左右反転|좌우 뒤집기|Inverter horizontalmente|Отразить по горизонтали|Yatay çevir|水平翻转|水平翻轉
Fade in|Fondu entrant|Dissolvenza in entrata|フェードイン|페이드 인|Entrada gradual|Появление|Açılma|淡入|淡入
Fade out|Fondu sortant|Dissolvenza in uscita|フェードアウト|페이드 아웃|Saída gradual|Затухание|Kararma|淡出|淡出
Screen color|Couleur à supprimer|Colore da rimuovere|背景色|제거할 색상|Cor a remover|Удаляемый цвет|Kaldırılacak renk|背景颜色|背景顏色
Similarity|Similarité|Somiglianza|類似度|유사도|Similaridade|Сходство|Benzerlik|相似度|相似度
Select|Sélectionner|Seleziona|選択|선택|Selecionar|Выбрать|Seç|选择|選取
Blade|Lame|Lama|カット|자르기|Lâmina|Лезвие|Bıçak|刀片|刀片
Split at playhead|Couper à la tête de lecture|Dividi al cursore|再生位置で分割|재생 헤드에서 분할|Dividir no cursor|Разделить на позиции курсора|Oynatma kafasında böl|在播放头处分割|在播放頭分割
Detach audio|Détacher l’audio|Separa audio|音声を分離|오디오 분리|Separar áudio|Отделить аудио|Sesi ayır|分离音频|分離音訊
Snap|Magnétisme|Aggancio|スナップ|맞춤|Encaixe|Привязка|Yakala|吸附|吸附
Add title|Ajouter un titre|Aggiungi titolo|タイトルを追加|제목 추가|Adicionar título|Добавить заголовок|Başlık ekle|添加标题|新增標題
Transcribe selected clip|Transcrire le clip sélectionné|Trascrivi clip selezionata|選択クリップを文字起こし|선택 클립 받아쓰기|Transcrever clipe selecionado|Расшифровать выбранный клип|Seçili klibi yazıya dök|转录所选片段|轉錄所選片段
Speak selected title|Lire le titre sélectionné|Leggi titolo selezionato|選択タイトルを読み上げ|선택 제목 읽기|Ler título selecionado|Озвучить выбранный заголовок|Seçili başlığı seslendir|朗读所选标题|朗讀所選標題
Duration|Durée|Durata|長さ|길이|Duração|Длительность|Süre|时长|時長
Crossfade|Fondu enchaîné|Dissolvenza incrociata|クロスフェード|크로스페이드|Dissolução cruzada|Перекрёстное затухание|Çapraz geçiş|交叉淡化|交叉淡化
Dip to black|Fondu au noir|Dissolvenza al nero|暗転|검정으로 전환|Transição pelo preto|Через чёрный|Siyaha geçiş|淡入黑场|淡入黑場
Stock media|Banque de médias|Archivio multimediale|素材ライブラリ|스톡 미디어|Banco de mídia|Медиатека|Stok medya|素材库|素材庫
Search|Rechercher|Cerca|検索|검색|Pesquisar|Поиск|Ara|搜索|搜尋
Close|Fermer|Chiudi|閉じる|닫기|Fechar|Закрыть|Kapat|关闭|關閉
Import URL|Importer une URL|Importa URL|URLから読み込み|URL 가져오기|Importar URL|Импорт URL|URL içe aktar|导入链接|匯入連結
Video|Vidéo|Video|動画|동영상|Vídeo|Видео|Video|视频|影片
Photos|Photos|Foto|写真|사진|Fotos|Фото|Fotoğraflar|照片|照片
Export video|Exporter la vidéo|Esporta video|動画を書き出し|동영상 내보내기|Exportar vídeo|Экспорт видео|Videoyu dışa aktar|导出视频|匯出影片
Format|Format|Formato|形式|형식|Formato|Формат|Biçim|格式|格式
Quality|Qualité|Qualità|品質|품질|Qualidade|Качество|Kalite|质量|品質
Start export|Lancer l’export|Avvia esportazione|書き出し開始|내보내기 시작|Iniciar exportação|Начать экспорт|Dışa aktarmayı başlat|开始导出|開始匯出
Cancel|Annuler|Annulla|キャンセル|취소|Cancelar|Отмена|İptal|取消|取消
Project saved|Projet enregistré|Progetto salvato|保存しました|프로젝트 저장됨|Projeto salvo|Проект сохранён|Proje kaydedildi|项目已保存|專案已儲存
Save failed|Échec de l’enregistrement|Salvataggio non riuscito|保存できませんでした|저장 실패|Falha ao salvar|Не удалось сохранить|Kaydetme başarısız|保存失败|儲存失敗
Templates|Modèles|Modelli|テンプレート|템플릿|Modelos|Шаблоны|Şablonlar|模板|範本
Mute audio|Couper le son|Disattiva audio|音声をミュート|오디오 음소거|Silenciar áudio|Отключить звук|Sesi kapat|音频静音|音訊靜音
English|Anglais|Inglese|英語|영어|Inglês|Английский|İngilizce|英语|英語
Auto (multilingual)|Auto (multilingue)|Auto (multilingue)|自動（多言語）|자동 (다국어)|Auto (multilíngue)|Авто (многоязычный)|Otomatik (çok dilli)|自动（多语言）|自動（多語言）
Track|Piste|Traccia|トラック|트랙|Faixa|Дорожка|İz|轨道|軌道
Voice|Voix|Voce|声|음성|Voz|Голос|Ses|声音|聲音
Default voice|Voix par défaut|Voce predefinita|標準の声|기본 음성|Voz padrão|Голос по умолчанию|Varsayılan ses|默认声音|預設聲音
Select a text clip first|Sélectionnez un clip de texte|Seleziona una clip di testo|テキストクリップを選択してください|텍스트 클립을 선택하세요|Selecione um clipe de texto|Выберите текстовый клип|Önce metin klibi seçin|请先选择文字片段|請先選取文字片段
Select a video or audio clip first|Sélectionnez un clip vidéo ou audio|Seleziona una clip video o audio|動画または音声クリップを選択してください|동영상이나 오디오 클립을 선택하세요|Selecione um clipe de vídeo ou áudio|Выберите видео или аудиоклип|Önce video veya ses klibi seçin|请先选择视频或音频片段|請先選取影片或音訊片段
Generating speech|Synthèse vocale en cours|Generazione della voce|音声を生成中|음성 생성 중|Gerando fala|Создание речи|Ses oluşturuluyor|正在生成语音|正在產生語音
Speech added to the audio track|Voix ajoutée à la piste audio|Voce aggiunta alla traccia audio|音声トラックに追加しました|오디오 트랙에 음성 추가됨|Fala adicionada à faixa de áudio|Речь добавлена на аудиодорожку|Ses izine konuşma eklendi|语音已添加到音轨|語音已新增至音軌
Network error|Erreur réseau|Errore di rete|ネットワークエラー|네트워크 오류|Erro de rede|Ошибка сети|Ağ hatası|网络错误|網路錯誤
Prev|Précédent|Precedente|前へ|이전|Anterior|Назад|Önceki|上一页|上一頁
Next|Suivant|Successivo|次へ|다음|Próximo|Далее|Sonraki|下一页|下一頁
Searching|Recherche en cours|Ricerca in corso|検索中|검색 중|Pesquisando|Поиск|Aranıyor|正在搜索|正在搜尋
No results|Aucun résultat|Nessun risultato|結果がありません|결과 없음|Nenhum resultado|Нет результатов|Sonuç yok|无结果|沒有結果
Importing|Import en cours|Importazione in corso|読み込み中|가져오는 중|Importando|Импорт|İçe aktarılıyor|正在导入|正在匯入
Imported to bin|Ajouté au chutier|Aggiunto alla raccolta|メディアに追加しました|미디어함에 추가됨|Importado para a coleção|Добавлено в медиатеку|Medyaya eklendi|已导入媒体库|已匯入媒體庫
Import failed|Échec de l’import|Importazione non riuscita|読み込めませんでした|가져오기 실패|Falha ao importar|Не удалось импортировать|İçe aktarma başarısız|导入失败|匯入失敗
Downloading|Téléchargement en cours|Download in corso|ダウンロード中|다운로드 중|Baixando|Загрузка|İndiriliyor|正在下载|正在下載
Mask|Masque|Maschera|マスク|마스크|Máscara|Маска|Maske|蒙版|遮罩
Shape|Forme|Forma|形状|모양|Forma|Форма|Şekil|形状|形狀
None|Aucun|Nessuno|なし|없음|Nenhum|Нет|Yok|无|無
Rectangle|Rectangle|Rettangolo|長方形|직사각형|Retângulo|Прямоугольник|Dikdörtgen|矩形|矩形
Ellipse|Ellipse|Ellisse|楕円|타원|Elipse|Эллипс|Elips|椭圆|橢圓
Left|Gauche|Sinistra|左|왼쪽|Esquerda|Слева|Sol|左侧|左側
Top|Haut|Alto|上|위쪽|Topo|Сверху|Üst|顶部|頂部
Feather|Contour progressif|Sfumatura|ぼかし幅|가장자리 흐림|Suavização|Растушёвка|Yumuşatma|羽化|羽化
Voice filter|Filtre vocal|Filtro vocale|音声フィルター|음성 필터|Filtro de voz|Голосовой фильтр|Ses filtresi|语音滤镜|語音濾鏡
Pitch up|Voix plus aiguë|Tono più alto|声を高く|높은 음정|Tom mais alto|Повысить тон|Tonu yükselt|升调|升調
Pitch down|Voix plus grave|Tono più basso|声を低く|낮은 음정|Tom mais baixo|Понизить тон|Tonu düşür|降调|降調
Echo|Écho|Eco|エコー|에코|Eco|Эхо|Yankı|回声|回聲
Radio|Radio|Radio|ラジオ|라디오|Rádio|Радио|Radyo|收音机|收音機
Preset name|Nom du préréglage|Nome predefinito|プリセット名|프리셋 이름|Nome da predefinição|Имя пресета|Ön ayar adı|预设名称|預設名稱
Save style from selected clip|Enregistrer le style du clip|Salva stile della clip|選択クリップのスタイルを保存|선택 클립 스타일 저장|Salvar estilo do clipe|Сохранить стиль клипа|Klip stilini kaydet|保存所选片段样式|儲存所選片段樣式
Import .fcpreset|Importer .fcpreset|Importa .fcpreset|.fcpreset を読み込み|.fcpreset 가져오기|Importar .fcpreset|Импорт .fcpreset|.fcpreset içe aktar|导入 .fcpreset|匯入 .fcpreset
Select a clip first|Sélectionnez un clip|Seleziona una clip|クリップを選択してください|클립을 선택하세요|Selecione um clipe|Выберите клип|Önce bir klip seçin|请先选择片段|請先選取片段
Preset saved|Préréglage enregistré|Predefinito salvato|プリセットを保存しました|프리셋 저장됨|Predefinição salva|Пресет сохранён|Ön ayar kaydedildi|预设已保存|預設已儲存
Style applied|Style appliqué|Stile applicato|スタイルを適用しました|스타일 적용됨|Estilo aplicado|Стиль применён|Stil uygulandı|样式已应用|樣式已套用
Preset imported|Préréglage importé|Predefinito importato|プリセットを読み込みました|프리셋 가져옴|Predefinição importada|Пресет импортирован|Ön ayar içe aktarıldı|预设已导入|預設已匯入
Track motion to keyframes|Suivre le mouvement en images clés|Traccia movimento in fotogrammi chiave|動きをキーフレームに追跡|동작을 키프레임으로 추적|Rastrear movimento em quadros-chave|Отследить движение в ключевые кадры|Hareketi anahtar karelere izle|跟踪运动并生成关键帧|追蹤運動並產生關鍵影格
Click the subject on the stage|Cliquez sur le sujet dans l’aperçu|Fai clic sul soggetto nell’anteprima|プレビューの被写体をクリック|미리보기에서 대상을 클릭하세요|Clique no objeto na prévia|Нажмите на объект в окне просмотра|Önizlemede nesneye tıklayın|点击预览中的主体|點擊預覽中的主體
Select a clip to animate first|Sélectionnez le clip à animer|Seleziona la clip da animare|動かすクリップを選択してください|애니메이션할 클립을 선택하세요|Selecione o clipe para animar|Выберите клип для анимации|Önce canlandırılacak klibi seçin|请先选择要添加动画的片段|請先選取要加入動畫的片段
No video clip under the playhead to track|Aucune vidéo à suivre à cette position|Nessun video da tracciare in questa posizione|再生位置に追跡する動画がありません|재생 헤드에 추적할 동영상이 없습니다|Nenhum vídeo para rastrear nesta posição|Нет видео для отслеживания на курсоре|Bu konumda izlenecek video yok|播放头处没有可跟踪的视频|播放頭處沒有可追蹤的影片
Pick a point inside the video|Choisissez un point dans la vidéo|Scegli un punto nel video|動画の内部を選択してください|동영상 내부의 점을 선택하세요|Escolha um ponto dentro do vídeo|Выберите точку внутри видео|Video içinde bir nokta seçin|请选择视频内的点|請選取影片內的點
Tracking|Suivi en cours|Tracciamento in corso|追跡中|추적 중|Rastreando|Отслеживание|İzleniyor|正在跟踪|正在追蹤
Tracking failed|Échec du suivi|Tracciamento non riuscito|追跡できませんでした|추적 실패|Falha no rastreamento|Не удалось отследить|İzleme başarısız|跟踪失败|追蹤失敗
keyframes added|images clés ajoutées|fotogrammi chiave aggiunti|キーフレームを追加しました|키프레임 추가됨|quadros-chave adicionados|ключевых кадров добавлено|anahtar kare eklendi|个关键帧已添加|個關鍵影格已新增
Titles land on the top track at the playhead.|Les titres sont ajoutés sur la piste supérieure à la tête de lecture.|I titoli vengono aggiunti alla traccia superiore al cursore.|タイトルは再生位置の最上位トラックに追加されます。|제목은 재생 헤드의 맨 위 트랙에 추가됩니다.|Os títulos são adicionados à faixa superior no cursor.|Заголовки добавляются на верхнюю дорожку в позиции курсора.|Başlıklar oynatma kafasında en üst ize eklenir.|标题会添加到播放头处的最上方轨道。|標題會新增至播放頭處的最上方軌道。
Captions: transcribe the selected clip's audio offline (Whisper runs in your browser; the model downloads once).|Sous-titres : transcription locale avec Whisper après le premier téléchargement du modèle.|Sottotitoli: trascrizione locale con Whisper dopo il primo download del modello.|字幕：モデルの初回ダウンロード後、Whisperで音声をローカル文字起こしします。|자막: 모델을 한 번 다운로드하면 Whisper로 로컬에서 받아씁니다.|Legendas: transcrição local com Whisper após baixar o modelo uma vez.|Субтитры: локальная расшифровка Whisper после первой загрузки модели.|Altyazılar: model bir kez indirildikten sonra Whisper ile yerel yazıya dökme.|字幕：首次下载模型后，Whisper 在本地转录音频。|字幕：首次下載模型後，Whisper 在本機轉錄音訊。
Applied to the selected clip's entry; crossfade extends the previous adjacent clip through the cut.|Appliqué au début du clip sélectionné. Le fondu prolonge le clip adjacent précédent.|Applicata all’inizio della clip. La dissolvenza estende la clip precedente adiacente.|選択クリップの開始に適用します。クロスフェードは隣接する前のクリップを延長します。|선택 클립 시작에 적용됩니다. 크로스페이드는 앞의 인접 클립을 연장합니다.|Aplicada ao início do clipe. A dissolução estende o clipe anterior adjacente.|Применяется к началу клипа. Переход продлевает предыдущий соседний клип.|Klibin başına uygulanır. Çapraz geçiş önceki bitişik klibi uzatır.|应用于所选片段开头；交叉淡化会延长前一个相邻片段。|套用於所選片段開頭；交叉淡化會延長前一個相鄰片段。
Select the clip to animate, press the button, then click the subject on the stage.|Sélectionnez le clip à animer, appuyez sur le bouton puis cliquez sur le sujet.|Seleziona la clip, premi il pulsante e fai clic sul soggetto.|動かすクリップを選択し、ボタンを押してプレビューの被写体をクリックします。|클립을 선택하고 버튼을 누른 뒤 미리보기의 대상을 클릭하세요.|Selecione o clipe, pressione o botão e clique no objeto na prévia.|Выберите клип, нажмите кнопку, затем объект в окне просмотра.|Klibi seçin, düğmeye basın ve önizlemede nesneye tıklayın.|选择要添加动画的片段，按下按钮，再点击预览中的主体。|選取要加入動畫的片段，按下按鈕，再點擊預覽中的主體。
Preview and export use the same processing.|L’aperçu et l’export utilisent le même traitement.|Anteprima ed esportazione usano la stessa elaborazione.|プレビューと書き出しは同じ処理を使います。|미리보기와 내보내기는 같은 처리를 사용합니다.|Prévia e exportação usam o mesmo processamento.|Просмотр и экспорт используют одну обработку.|Önizleme ve dışa aktarma aynı işlemi kullanır.|预览和导出使用相同处理流程。|預覽和匯出使用相同處理流程。
Creator tools|Outils de création|Strumenti creativi|制作ツール|제작 도구|Ferramentas de criação|Инструменты создания|Oluşturma araçları|创作工具|創作工具
Speed curve|Courbe de vitesse|Curva di velocità|速度カーブ|속도 곡선|Curva de velocidade|Кривая скорости|Hız eğrisi|速度曲线|速度曲線
Motion presets|Préréglages de mouvement|Movimenti predefiniti|モーションプリセット|동작 프리셋|Movimentos predefinidos|Пресеты движения|Hareket ön ayarları|运动预设|運動預設
Visual effects|Effets visuels|Effetti visivi|視覚効果|시각 효과|Efeitos visuais|Визуальные эффекты|Görsel efektler|视觉效果|視覺效果
Audio processing|Traitement audio|Elaborazione audio|音声処理|오디오 처리|Processamento de áudio|Обработка аудио|Ses işleme|音频处理|音訊處理
Cutout and brushes|Détourage et pinceaux|Ritaglio e pennelli|切り抜きとブラシ|배경 제거 및 브러시|Recorte e pincéis|Вырезка и кисти|Kesme ve fırçalar|抠图和画笔|去背與筆刷
LUT, shader and expressions|LUT, shader et expressions|LUT, shader ed espressioni|LUT・シェーダー・式|LUT, 셰이더 및 수식|LUT, shader e expressões|LUT, шейдер и выражения|LUT, gölgelendirici ve ifadeler|LUT、着色器和表达式|LUT、著色器與運算式
Apply curve|Appliquer la courbe|Applica curva|カーブを適用|곡선 적용|Aplicar curva|Применить кривую|Eğriyi uygula|应用曲线|套用曲線
Constant speed|Vitesse constante|Velocità costante|一定速度|일정 속도|Velocidade constante|Постоянная скорость|Sabit hız|恒定速度|固定速度
Apply keyframes|Appliquer les images clés|Applica fotogrammi chiave|キーフレームを適用|키프레임 적용|Aplicar quadros-chave|Применить ключевые кадры|Anahtar kareleri uygula|应用关键帧|套用關鍵影格
Add effect|Ajouter un effet|Aggiungi effetto|エフェクトを追加|효과 추가|Adicionar efeito|Добавить эффект|Efekt ekle|添加效果|新增效果
Remove|Retirer|Rimuovi|削除|제거|Remover|Удалить|Kaldır|移除|移除
Up|Monter|Su|上へ|위로|Subir|Вверх|Yukarı|上移|上移
Volume|Volume|Volume|音量|음량|Volume|Громкость|Ses düzeyi|音量|音量
Pan|Panoramique|Panorama|パン|팬|Panorâmica|Панорама|Pan|声像|聲像
Add processor|Ajouter un traitement|Aggiungi elaborazione|音声処理を追加|처리 추가|Adicionar processamento|Добавить обработку|İşlem ekle|添加处理器|新增處理器
Apply transition|Appliquer la transition|Applica transizione|トランジションを適用|전환 적용|Aplicar transição|Применить переход|Geçişi uygula|应用转场|套用轉場
Object cutout|Détourage d’objet|Ritaglio oggetto|物体の切り抜き|물체 배경 제거|Recorte de objeto|Вырезка объекта|Nesne kesme|物体抠图|物件去背
Person cutout|Détourage de personne|Ritaglio persona|人物の切り抜き|인물 배경 제거|Recorte de pessoa|Вырезка человека|Kişi kesme|人物抠图|人物去背
Enable cutout|Activer le détourage|Attiva ritaglio|切り抜きを有効化|배경 제거 사용|Ativar recorte|Включить вырезку|Kesmeyi etkinleştir|启用抠图|啟用去背
Remove cutout|Retirer le détourage|Rimuovi ritaglio|切り抜きを解除|배경 제거 해제|Remover recorte|Отключить вырезку|Kesmeyi kaldır|移除抠图|移除去背
Restore|Restaurer|Ripristina|復元|복원|Restaurar|Восстановить|Geri yükle|恢复|還原
Erase|Effacer|Cancella|消去|지우기|Apagar|Стереть|Sil|擦除|擦除
Off|Désactivé|Disattivato|オフ|끄기|Desativado|Выкл.|Kapalı|关闭|關閉
Project|Projet|Progetto|プロジェクト|프로젝트|Projeto|Проект|Proje|项目|專案
Timeline templates|Modèles de montage|Modelli di montaggio|タイムラインテンプレート|타임라인 템플릿|Modelos de linha do tempo|Шаблоны таймлайна|Zaman çizelgesi şablonları|时间线模板|時間軸範本
Local speech|Voix locale|Voce locale|ローカル音声合成|로컬 음성 합성|Fala local|Локальная речь|Yerel konuşma|本地语音|本機語音
Local models|Modèles locaux|Modelli locali|ローカルモデル|로컬 모델|Modelos locais|Локальные модели|Yerel modeller|本地模型|本機模型
Project settings|Paramètres du projet|Impostazioni progetto|プロジェクト設定|프로젝트 설정|Configurações do projeto|Параметры проекта|Proje ayarları|项目设置|專案設定
Apply settings|Appliquer les paramètres|Applica impostazioni|設定を適用|설정 적용|Aplicar configurações|Применить параметры|Ayarları uygula|应用设置|套用設定
Add track|Ajouter une piste|Aggiungi traccia|トラックを追加|트랙 추가|Adicionar faixa|Добавить дорожку|İz ekle|添加轨道|新增軌道
Add timeline|Ajouter un montage|Aggiungi sequenza|タイムラインを追加|타임라인 추가|Adicionar linha do tempo|Добавить таймлайн|Zaman çizelgesi ekle|添加时间线|新增時間軸
Create project|Créer un projet|Crea progetto|プロジェクトを作成|프로젝트 만들기|Criar projeto|Создать проект|Proje oluştur|创建项目|建立專案
Download|Télécharger|Scarica|ダウンロード|다운로드|Baixar|Скачать|İndir|下载|下載
Cancel job|Annuler la tâche|Annulla attività|処理をキャンセル|작업 취소|Cancelar tarefa|Отменить задачу|İşi iptal et|取消任务|取消工作
Ready offline|Prêt hors ligne|Pronto offline|オフライン利用可|오프라인 사용 가능|Pronto offline|Готово офлайн|Çevrimdışı hazır|可离线使用|可離線使用
Not installed|Non installé|Non installato|未インストール|설치되지 않음|Não instalado|Не установлено|Yüklü değil|未安装|未安裝
Preview|Aperçu|Anteprima|プレビュー|미리보기|Prévia|Просмотр|Önizleme|预览|預覽
Full size|Taille réelle|Dimensione completa|フルサイズ|원본 크기|Tamanho completo|Полный размер|Tam boyut|完整尺寸|完整尺寸
Settings|Paramètres|Impostazioni|設定|설정|Configurações|Настройки|Ayarlar|设置|設定
Collapse the rail|Réduire la barre|Comprimi la barra|レールを折りたたむ|레일 접기|Recolher a barra|Свернуть панель|Şeridi daralt|折叠侧栏|折疊側欄
Project|Projet|Progetto|プロジェクト|프로젝트|Projeto|Проект|Proje|项目|專案
Playback|Lecture|Riproduzione|再生|재생|Reprodução|Воспроизведение|Oynatma|播放|播放
Appearance|Apparence|Aspetto|外観|외관|Aparência|Оформление|Görünüm|外观|外觀
Advanced|Avancé|Avanzate|詳細|고급|Avançado|Дополнительно|Gelişmiş|高级|進階
Frame|Image|Fotogramma|フレーム|프레임|Quadro|Кадр|Kare|画面|畫面
Applies to preview and export|S'applique à l'aperçu et à l'export|Vale per anteprima ed esportazione|プレビューと書き出しに適用|미리보기와 내보내기에 적용|Vale para pré-visualização e exportação|Применяется к просмотру и экспорту|Önizleme ve dışa aktarma için geçerli|应用于预览和导出|套用於預覽與匯出
Width|Largeur|Larghezza|幅|너비|Largura|Ширина|Genişlik|宽度|寬度
Height|Hauteur|Altezza|高さ|높이|Altura|Высота|Yükseklik|高度|高度
Frames per second|Images par seconde|Fotogrammi al secondo|フレーム毎秒|초당 프레임|Quadros por segundo|Кадров в секунду|Saniyedeki kare|每秒帧数|每秒影格
Preview|Aperçu|Anteprima|プレビュー|미리보기|Pré-visualização|Просмотр|Önizleme|预览|預覽
Smaller previews play faster|Un aperçu plus petit est plus fluide|Anteprime più piccole sono più fluide|小さいプレビューほど滑らかです|작은 미리보기가 더 빠릅니다|Pré-visualizações menores são mais rápidas|Меньший размер просмотра идёт быстрее|Küçük önizlemeler daha akıcı oynar|预览越小越流畅|預覽越小越流暢
Preview width|Largeur de l'aperçu|Larghezza anteprima|プレビュー幅|미리보기 너비|Largura da pré-visualização|Ширина просмотра|Önizleme genişliği|预览宽度|預覽寬度
Profiles|Profils|Profili|プロファイル|프로필|Perfis|Профили|Profiller|配置|設定檔
30 options, two of them random|30 options, dont deux aléatoires|30 opzioni, due casuali|30 種類、うち 2 つはランダム|30가지, 그중 2개는 무작위|30 opções, duas aleatórias|30 вариантов, два случайных|30 seçenek, ikisi rastgele|30 个选项，其中两个随机|30 個選項，其中兩個隨機
Accent colour|Couleur d'accent|Colore d'accento|アクセントカラー|강조 색상|Cor de destaque|Акцентный цвет|Vurgu rengi|强调色|強調色
Recolours icons and controls|Recolore icônes et contrôles|Ricolora icone e controlli|アイコンとコントロールの色を変えます|아이콘과 컨트롤의 색을 바꿉니다|Recolore ícones e controles|Перекрашивает значки и элементы|Simgeleri ve denetimleri yeniden renklendirir|重新着色图标与控件|重新著色圖示與控制項
Match the profile|Suivre le profil|Segui il profilo|プロファイルに合わせる|프로필에 맞춤|Seguir o perfil|Как в профиле|Profille eşleştir|跟随配置|跟隨設定檔
API keys|Clés d'API|Chiavi API|API キー|API 키|Chaves de API|Ключи API|API anahtarları|API 密钥|API 金鑰
Read from the environment|Lues dans l'environnement|Lette dall'ambiente|環境から読み込みます|환경에서 읽습니다|Lidas do ambiente|Читаются из окружения|Ortamdan okunur|从环境读取|從環境讀取
Keys live in .env beside the launcher, never in a project. Copy example.env to .env and restart to change them.|Les clés vivent dans .env à côté du lanceur, jamais dans un projet. Copiez example.env vers .env puis redémarrez.|Le chiavi stanno in .env accanto al launcher, mai in un progetto. Copia example.env in .env e riavvia.|キーはランチャー横の .env にあり、プロジェクトには入りません。example.env を .env にコピーして再起動してください。|키는 실행기 옆 .env에 있으며 프로젝트에는 없습니다. example.env를 .env로 복사한 뒤 재시작하세요.|As chaves ficam em .env ao lado do iniciador, nunca em um projeto. Copie example.env para .env e reinicie.|Ключи лежат в .env рядом с запускателем, не в проекте. Скопируйте example.env в .env и перезапустите.|Anahtarlar başlatıcının yanındaki .env dosyasında durur, projede değil. example.env dosyasını .env olarak kopyalayıp yeniden başlatın.|密钥位于启动器旁的 .env 中，不在项目里。将 example.env 复制为 .env 后重启。|金鑰位於啟動器旁的 .env 中，不在專案裡。將 example.env 複製為 .env 後重新啟動。
Reset|Réinitialiser|Ripristina|リセット|초기화|Redefinir|Сброс|Sıfırla|重置|重設
Local to this browser|Local à ce navigateur|Locale a questo browser|このブラウザーのみ|이 브라우저에만 적용|Local a este navegador|Только в этом браузере|Bu tarayıcıya özel|仅限本浏览器|僅限本瀏覽器
Reset appearance|Réinitialiser l'apparence|Ripristina aspetto|外観をリセット|외관 초기화|Redefinir aparência|Сбросить оформление|Görünümü sıfırla|重置外观|重設外觀
Focus the preview|Mettre l'aperçu en avant|Metti l'anteprima in primo piano|プレビューを大きく表示|미리보기 집중|Focar a pré-visualização|Развернуть просмотр|Önizlemeye odakla|聚焦预览|聚焦預覽
Panels|Panneaux|Pannelli|パネル|패널|Painéis|Панели|Bölmeler|面板|面板
Close|Fermer|Chiudi|閉じる|닫기|Fechar|Закрыть|Kapat|关闭|關閉
Resize the media panel|Redimensionner le panneau des médias|Ridimensiona il pannello media|メディアパネルのサイズを変更|미디어 패널 크기 조절|Redimensionar o painel de mídia|Изменить размер панели медиа|Medya panelini yeniden boyutlandır|调整媒体面板大小|調整媒體面板大小
Resize the inspector|Redimensionner l'inspecteur|Ridimensiona l'ispettore|インスペクターのサイズを変更|인스펙터 크기 조절|Redimensionar o inspetor|Изменить размер инспектора|Denetçiyi yeniden boyutlandır|调整检查器大小|調整檢閱器大小
Resize the timeline|Redimensionner la timeline|Ridimensiona la timeline|タイムラインのサイズを変更|타임라인 크기 조절|Redimensionar a linha do tempo|Изменить размер таймлайна|Zaman çizelgesini yeniden boyutlandır|调整时间线大小|調整時間軸大小
Swap the side panels|Échanger les panneaux latéraux|Scambia i pannelli laterali|サイドパネルを入れ替え|사이드 패널 교체|Trocar os painéis laterais|Поменять боковые панели|Yan bölmeleri değiştir|交换侧边面板|交換側邊面板
Timeline on top|Timeline en haut|Timeline in alto|タイムラインを上に|타임라인을 위로|Linha do tempo no topo|Таймлайн сверху|Zaman çizelgesi üstte|时间线置顶|時間軸置頂
Keyframes|Images clés|Fotogrammi chiave|キーフレーム|키프레임|Quadros-chave|Ключевые кадры|Anahtar kareler|关键帧|關鍵影格
Lanes|Pistes|Corsie|レーン|레인|Faixas|Дорожки|Şeritler|轨道|軌道
Curve|Courbe|Curva|カーブ|커브|Curva|Кривая|Eğri|曲线|曲線
Eased curves|Courbes lissées|Curve morbide|イージング曲線|이징 곡선|Curvas suavizadas|Сглаженные кривые|Yumuşatılmış eğriler|缓动曲线|緩動曲線
Property for the curve|Propriété de la courbe|Proprietà della curva|カーブのプロパティ|커브 속성|Propriedade da curva|Свойство для кривой|Eğri için özellik|曲线属性|曲線屬性
Click a lane to add, drag to move, alt-click to remove, double-click to change easing|Cliquez pour ajouter, glissez pour déplacer, alt-clic pour supprimer, double-clic pour l'accélération|Clic per aggiungere, trascina per spostare, alt-clic per rimuovere, doppio clic per l'easing|クリックで追加、ドラッグで移動、Alt クリックで削除、ダブルクリックでイージング変更|클릭하여 추가, 드래그로 이동, Alt 클릭으로 삭제, 더블 클릭으로 이징 변경|Clique para adicionar, arraste para mover, alt-clique para remover, duplo clique para a suavização|Щёлкните, чтобы добавить, тяните, чтобы сдвинуть, Alt-щелчок удаляет, двойной щелчок меняет плавность|Eklemek için tıklayın, taşımak için sürükleyin, kaldırmak için alt-tıklayın, yumuşatma için çift tıklayın|点击添加，拖动移动，alt 点击删除，双击更改缓动|點擊新增，拖曳移動，alt 點擊刪除，雙擊變更緩動
Select a clip to see its keyframes|Sélectionnez un clip pour voir ses images clés|Seleziona una clip per vederne i fotogrammi chiave|クリップを選ぶとキーフレームが表示されます|클립을 선택하면 키프레임이 표시됩니다|Selecione um clipe para ver seus quadros-chave|Выберите клип, чтобы увидеть его ключевые кадры|Anahtar karelerini görmek için bir klip seçin|选择片段以查看其关键帧|選擇片段以檢視其關鍵影格
AI providers|Fournisseurs d'IA|Fornitori di IA|AI プロバイダー|AI 제공자|Provedores de IA|Поставщики ИИ|Yapay zeka sağlayıcıları|AI 提供方|AI 供應商
No key|Aucune clé|Nessuna chiave|キーなし|키 없음|Sem chave|Нет ключа|Anahtar yok|无密钥|無金鑰
Key set|Clé enregistrée|Chiave salvata|キー設定済み|키 설정됨|Chave definida|Ключ задан|Anahtar ayarlı|已设置密钥|已設定金鑰
Connected|Connecté|Connesso|接続済み|연결됨|Conectado|Подключено|Bağlandı|已连接|已連線
Failed|Échec|Non riuscito|失敗|실패|Falhou|Ошибка|Başarısız|失败|失敗
Testing the connection|Test de la connexion|Test della connessione|接続をテスト中|연결 테스트 중|Testando a conexão|Проверка подключения|Bağlantı test ediliyor|正在测试连接|正在測試連線
Save key|Enregistrer la clé|Salva la chiave|キーを保存|키 저장|Salvar chave|Сохранить ключ|Anahtarı kaydet|保存密钥|儲存金鑰
Test|Tester|Prova|テスト|테스트|Testar|Проверить|Test et|测试|測試
Remove|Supprimer|Rimuovi|削除|삭제|Remover|Удалить|Kaldır|移除|移除
Paste the key|Collez la clé|Incolla la chiave|キーを貼り付け|키를 붙여넣기|Cole a chave|Вставьте ключ|Anahtarı yapıştır|粘贴密钥|貼上金鑰
Stored by the engine|Enregistrée par le moteur|Salvata dal motore|エンジンが保存|엔진이 저장|Guardada pelo motor|Хранится движком|Motor tarafından saklanıyor|由引擎保存|由引擎儲存
From the environment|Depuis l'environnement|Dall'ambiente|環境から|환경에서|Do ambiente|Из окружения|Ortamdan|来自环境|來自環境
Not configured|Non configurée|Non configurata|未設定|미설정|Não configurada|Не настроен|Yapılandırılmadı|未配置|未設定
Add one here, or set|Ajoutez-en une ici ou définissez|Aggiungine una qui o imposta|ここで追加、または設定|여기에 추가하거나 설정|Adicione uma aqui ou defina|Добавьте здесь или задайте|Buraya ekleyin veya ayarlayın|在此添加，或设置|在此新增，或設定
Stock photos and video|Photos et vidéos de stock|Foto e video stock|ストック写真と動画|스톡 사진과 영상|Fotos e vídeos de banco|Стоковые фото и видео|Stok fotoğraf ve video|图库照片与视频|圖庫照片與影片
Hosted speech|Voix hébergée|Voce ospitata|ホスト型音声|호스팅 음성|Voz hospedada|Облачная речь|Barındırılan konuşma|托管语音|託管語音
Keys are held by the engine, never by the browser and never in a project. A key set here overrides the environment and takes effect without a restart.|Les clés sont détenues par le moteur, jamais par le navigateur ni dans un projet. Une clé définie ici prime sur l'environnement et s'applique sans redémarrage.|Le chiavi stanno nel motore, mai nel browser né in un progetto. Una chiave impostata qui prevale sull'ambiente e vale senza riavvio.|キーはエンジンが保持し、ブラウザーやプロジェクトには残りません。ここで設定したキーは環境より優先され、再起動なしで有効になります。|키는 엔진이 보관하며 브라우저나 프로젝트에는 저장되지 않습니다. 여기서 설정한 키가 환경보다 우선하며 재시작 없이 적용됩니다.|As chaves ficam no motor, nunca no navegador nem em um projeto. Uma chave definida aqui prevalece sobre o ambiente e vale sem reiniciar.|Ключи хранит движок, не браузер и не проект. Заданный здесь ключ важнее окружения и работает без перезапуска.|Anahtarlar motorda tutulur, tarayıcıda veya projede değil. Burada ayarlanan anahtar ortamdan önce gelir ve yeniden başlatma gerektirmez.|密钥由引擎保存，不在浏览器也不在项目中。此处设置的密钥优先于环境变量，且无需重启即生效。|金鑰由引擎保存，不在瀏覽器也不在專案中。此處設定的金鑰優先於環境變數，且無需重新啟動即生效。
Generate speech|Générer la voix|Genera la voce|音声を生成|음성 생성|Gerar voz|Создать речь|Konuşma oluştur|生成语音|產生語音
Lands an audio clip at the playhead|Place un clip audio à la tête de lecture|Inserisce una clip audio alla testina|再生ヘッドに音声クリップを配置|재생 헤드에 오디오 클립을 배치|Coloca um clipe de áudio no cursor|Добавляет аудиоклип на позицию плейхеда|Oynatma kafasına bir ses klibi ekler|在播放头处添加音频片段|在播放磁頭處新增音訊片段
What should it say|Que doit-il dire|Cosa deve dire|読み上げる内容|무엇을 말할지|O que deve dizer|Что произнести|Ne söylenecek|要说的内容|要說的內容
Generate|Générer|Genera|生成|생성|Gerar|Создать|Oluştur|生成|產生
Asking the provider|Interrogation du fournisseur|Richiesta al fornitore|プロバイダーに問い合わせ中|제공자에 요청 중|Consultando o provedor|Запрос к поставщику|Sağlayıcıya soruluyor|正在请求提供方|正在請求供應商
Added to the timeline|Ajouté à la timeline|Aggiunto alla timeline|タイムラインに追加しました|타임라인에 추가했습니다|Adicionado à linha do tempo|Добавлено на таймлайн|Zaman çizelgesine eklendi|已添加到时间线|已新增至時間軸
Saved in Media; the active timeline changed|Enregistré dans Médias ; la timeline active a changé|Salvato in Media; la timeline attiva è cambiata|メディアに保存しました。アクティブなタイムラインが変わりました|미디어에 저장했습니다. 활성 타임라인이 변경되었습니다|Salvo em Mídia; a linha do tempo ativa mudou|Сохранено в медиа; активный таймлайн изменился|Medya'ya kaydedildi; etkin zaman çizelgesi değişti|已保存到媒体；活动时间线已更改|已儲存至媒體；使用中的時間軸已變更
Projects|Projets|Progetti|プロジェクト|프로젝트|Projetos|Проекты|Projeler|项目|專案
Media|Médias|Media|メディア|미디어|Mídia|Медиа|Medya|媒体|媒體
Templates|Modèles|Modelli|テンプレート|템플릿|Modelos|Шаблоны|Şablonlar|模板|範本
Models|Modèles locaux|Modelli|モデル|모델|Modelos de IA|Модели|Modeller|模型|模型
Storage|Stockage|Spazio|ストレージ|저장 공간|Armazenamento|Хранилище|Depolama|存储|儲存空間
Search the library|Rechercher dans la bibliothèque|Cerca nella libreria|ライブラリを検索|라이브러리 검색|Pesquisar na biblioteca|Поиск в библиотеке|Kitaplıkta ara|搜索媒体库|搜尋媒體庫
Interface language|Langue de l'interface|Lingua dell'interfaccia|インターフェースの言語|인터페이스 언어|Idioma da interface|Язык интерфейса|Arayüz dili|界面语言|介面語言
Import files|Importer des fichiers|Importa file|ファイルを取り込む|파일 가져오기|Importar arquivos|Импортировать файлы|Dosya içe aktar|导入文件|匯入檔案
Importing|Importation|Importazione|取り込み中|가져오는 중|Importando|Импорт|İçe aktarılıyor|正在导入|正在匯入
Imported|Importé|Importati|取り込み完了|가져왔습니다|Importado|Импортировано|İçe aktarıldı|已导入|已匯入
Rename|Renommer|Rinomina|名前を変更|이름 변경|Renomear|Переименовать|Yeniden adlandır|重命名|重新命名
Renamed|Renommé|Rinominato|名前を変更しました|이름을 변경했습니다|Renomeado|Переименовано|Yeniden adlandırıldı|已重命名|已重新命名
Show file|Afficher le fichier|Mostra il file|ファイルを表示|파일 표시|Mostrar arquivo|Показать файл|Dosyayı göster|显示文件|顯示檔案
Delete|Supprimer|Elimina|削除|삭제|Excluir|Удалить|Sil|删除|刪除
Deleted|Supprimé|Eliminato|削除しました|삭제했습니다|Excluído|Удалено|Silindi|已删除|已刪除
That did not work|Cela n'a pas fonctionné|Non ha funzionato|うまくいきませんでした|실패했습니다|Isso não funcionou|Не получилось|Bu işe yaramadı|操作未成功|操作未成功
The engine is not responding|Le moteur ne répond pas|Il motore non risponde|エンジンが応答していません|엔진이 응답하지 않습니다|O motor não está respondendo|Движок не отвечает|Motor yanıt vermiyor|引擎无响应|引擎沒有回應
No saved projects yet|Aucun projet enregistré|Nessun progetto salvato|保存されたプロジェクトはありません|저장된 프로젝트가 없습니다|Nenhum projeto salvo ainda|Пока нет сохранённых проектов|Kayıtlı proje yok|尚无已保存的项目|尚無已儲存的專案
No media yet. Import files or drop them here.|Aucun média. Importez des fichiers ou déposez-les ici.|Nessun media. Importa file o trascinali qui.|メディアがありません。ファイルを取り込むか、ここにドロップしてください。|미디어가 없습니다. 파일을 가져오거나 여기에 놓으세요.|Sem mídia. Importe arquivos ou solte-os aqui.|Медиа нет. Импортируйте файлы или перетащите их сюда.|Medya yok. Dosya içe aktarın veya buraya bırakın.|暂无媒体。导入文件或拖放到此处。|尚無媒體。匯入檔案或拖放至此處。
Nothing matches that search|Aucun résultat pour cette recherche|Nessun risultato per questa ricerca|検索に一致するものがありません|검색과 일치하는 항목이 없습니다|Nada corresponde a essa pesquisa|Ничего не найдено|Bu aramayla eşleşen yok|没有匹配的结果|沒有相符的結果
No templates saved yet|Aucun modèle enregistré|Nessun modello salvato|保存されたテンプレートはありません|저장된 템플릿이 없습니다|Nenhum modelo salvo ainda|Пока нет шаблонов|Kayıtlı şablon yok|尚无已保存的模板|尚無已儲存的範本
No local models listed|Aucun modèle local|Nessun modello locale|ローカルモデルがありません|로컬 모델이 없습니다|Nenhum modelo local listado|Локальных моделей нет|Yerel model listelenmedi|未列出本地模型|未列出本機模型
All|Tout|Tutto|すべて|전체|Tudo|Все|Tümü|全部|全部
Video|Vidéo|Video|動画|비디오|Vídeo|Видео|Video|视频|影片
Audio|Audio|Audio|音声|오디오|Áudio|Аудио|Ses|音频|音訊
Images|Images|Immagini|画像|이미지|Imagens|Изображения|Görseller|图片|圖片
slots|emplacements|slot|スロット|슬롯|espaços|слотов|yuva|插槽|插槽
installed|installé|installato|インストール済み|설치됨|instalado|установлено|kurulu|已安装|已安裝
not installed|non installé|non installato|未インストール|미설치|não instalado|не установлено|kurulu değil|未安装|未安裝
used|utilisé|usati|使用中|사용 중|usado|занято|kullanılıyor|已用|已用
reclaimable|récupérable|recuperabili|解放可能|회수 가능|recuperável|можно освободить|geri kazanılabilir|可回收|可回收
free on disk|libre sur le disque|liberi sul disco|ディスクの空き|디스크 여유 공간|livre no disco|свободно на диске|diskte boş|磁盘可用|磁碟可用
rebuildable|reconstructible|ricostruibile|再生成可能|다시 만들 수 있음|reconstruível|можно пересоздать|yeniden oluşturulabilir|可重建|可重建
Connections|Connexions|Connessioni|接続|연결|Conexões|Подключения|Bağlantılar|连接|連線
Orchestrators|Orchestrateurs|Orchestratori|オーケストレーター|오케스트레이터|Orquestradores|Оркестраторы|Orkestratörler|编排器|編排器
Systems driving this engine|Systèmes qui pilotent ce moteur|Sistemi che guidano questo motore|このエンジンを操作しているシステム|이 엔진을 제어하는 시스템|Sistemas que controlam este motor|Системы, управляющие движком|Bu motoru yönlendiren sistemler|正在驱动此引擎的系统|正在驅動此引擎的系統
Activity|Activité|Attività|アクティビティ|활동|Atividade|Активность|Etkinlik|活动|活動
Live from the event stream|En direct du flux d'événements|In diretta dal flusso di eventi|イベントストリームからのライブ|이벤트 스트림에서 실시간|Ao vivo do fluxo de eventos|В реальном времени из потока событий|Olay akışından canlı|来自事件流的实时信息|來自事件流的即時資訊
Nothing connected|Rien de connecté|Nulla collegato|接続なし|연결 없음|Nada conectado|Ничего не подключено|Bağlı bir şey yok|无连接|無連線
No jobs running|Aucune tâche en cours|Nessun lavoro in corso|実行中のジョブはありません|실행 중인 작업 없음|Nenhum trabalho em execução|Нет активных задач|Çalışan iş yok|没有运行中的任务|沒有執行中的工作
calls|appels|chiamate|呼び出し|호출|chamadas|вызовов|çağrı|次调用|次呼叫
Cancel|Annuler|Annulla|キャンセル|취소|Cancelar|Отменить|İptal|取消|取消
running|en cours|in corso|実行中|실행 중|em execução|выполняется|çalışıyor|运行中|執行中
finished|terminé|completato|完了|완료|concluído|завершено|tamamlandı|已完成|已完成
cancelled|annulé|annullato|キャンセル済み|취소됨|cancelado|отменено|iptal edildi|已取消|已取消
failed|échec|non riuscito|失敗|실패|falhou|ошибка|başarısız|失败|失敗
queued|en attente|in coda|待機中|대기 중|na fila|в очереди|kuyrukta|排队中|排隊中
Library|Bibliothèque|Libreria|ライブラリ|라이브러리|Biblioteca|Библиотека|Kitaplık|媒体库|媒體庫
items|éléments|elementi|件|개|itens|элементов|öğe|项|項
Interface mode|Mode d'interface|Modalità interfaccia|インターフェイスモード|인터페이스 모드|Modo de interface|Режим интерфейса|Arayüz modu|界面模式|介面模式
Easy|Simple|Facile|かんたん|쉬움|Fácil|Простой|Kolay|简易|簡易
Labelled tools, galleries and a magnetic main track|Outils étiquetés, galeries et piste principale magnétique|Strumenti con etichetta, gallerie e traccia principale magnetica|ラベル付きツール、ギャラリー、マグネットメイントラック|라벨이 있는 도구, 갤러리, 자석 메인 트랙|Ferramentas com rótulo, galerias e trilha principal magnética|Подписанные инструменты, галереи и магнитная главная дорожка|Etiketli araçlar, galeriler ve manyetik ana parça|带标签的工具、图库和磁性主轨道|帶標籤的工具、圖庫和磁性主軌道
Every pane, tab, tool and setting, arranged as today|Tous les panneaux, onglets, outils et réglages, disposés comme aujourd'hui|Ogni pannello, scheda, strumento e impostazione, disposti come oggi|すべてのパネル、タブ、ツール、設定を現在の配置で|모든 패널, 탭, 도구, 설정을 지금 그대로|Todos os painéis, abas, ferramentas e ajustes, como hoje|Все панели, вкладки, инструменты и настройки как сейчас|Bugünkü düzende tüm paneller, sekmeler, araçlar ve ayarlar|所有面板、标签、工具和设置，保持现有布局|所有面板、分頁、工具和設定，保持現有配置
Your profiles|Vos profils|I tuoi profili|あなたのプロファイル|내 프로필|Seus perfis|Ваши профили|Profilleriniz|你的配置|你的設定檔
Customise|Personnaliser|Personalizza|カスタマイズ|사용자 지정|Personalizar|Настроить|Özelleştir|自定义|自訂
Import profile|Importer un profil|Importa profilo|プロファイルを読み込む|프로필 가져오기|Importar perfil|Импортировать профиль|Profil içe aktar|导入配置|匯入設定檔
Export profile|Exporter le profil|Esporta profilo|プロファイルを書き出す|프로필 내보내기|Exportar perfil|Экспортировать профиль|Profili dışa aktar|导出配置|匯出設定檔
How do you want to edit?|Comment souhaitez-vous monter ?|Come vuoi montare?|どのように編集しますか？|어떻게 편집할까요?|Como você quer editar?|Как вы хотите монтировать?|Nasıl düzenlemek istersiniz?|你想如何编辑？|你想如何剪輯？
Unknown ids skipped|Identifiants inconnus ignorés|Id sconosciuti ignorati|不明なIDをスキップしました|알 수 없는 ID 건너뜀|Ids desconhecidos ignorados|Неизвестные идентификаторы пропущены|Bilinmeyen kimlikler atlandı|已跳过未知 ID|已略過未知 ID
Profile imported|Profil importé|Profilo importato|プロファイルを読み込みました|프로필을 가져왔습니다|Perfil importado|Профиль импортирован|Profil içe aktarıldı|配置已导入|設定檔已匯入
Delete profile|Supprimer le profil|Elimina profilo|プロファイルを削除|프로필 삭제|Excluir perfil|Удалить профиль|Profili sil|删除配置|刪除設定檔
Choose later in Settings|Modifiable plus tard dans Paramètres|Modificabile dopo nelle Impostazioni|設定で後から変更できます|설정에서 나중에 변경 가능|Mude depois em Configurações|Можно изменить позже в настройках|Daha sonra Ayarlar'dan değiştirin|稍后可在设置中更改|稍後可在設定中變更
Choose a format|Choisir un format|Scegli un formato|フォーマットを選択|형식 선택|Escolha um formato|Выберите формат|Bir format seçin|选择格式|選擇格式
Vertical|Vertical|Verticale|縦|세로|Vertical|Вертикальный|Dikey|竖屏|直式
Wide|Large|Largo|横|가로|Largo|Широкий|Geniş|横屏|橫式
Square|Carré|Quadrato|正方形|정사각형|Quadrado|Квадрат|Kare|方形|方形
Portrait|Portrait|Ritratto|ポートレート|세로 사진|Retrato|Портрет|Portre|肖像|肖像
Autosave|Enregistrement auto|Salvataggio automatico|自動保存|자동 저장|Salvamento automático|Автосохранение|Otomatik kaydet|自动保存|自動儲存
Save quietly a moment after each change|Enregistre discrètement peu après chaque modification|Salva in silenzio poco dopo ogni modifica|変更のたびに少し後で自動保存します|변경 후 잠시 뒤 조용히 저장|Salva discretamente logo após cada mudança|Тихо сохраняет вскоре после каждого изменения|Her değişiklikten kısa süre sonra sessizce kaydeder|每次更改后稍候自动保存|每次變更後稍候自動儲存
This project changed elsewhere|Ce projet a été modifié ailleurs|Questo progetto è cambiato altrove|このプロジェクトは別の場所で変更されました|이 프로젝트가 다른 곳에서 변경되었습니다|Este projeto foi alterado em outro lugar|Этот проект изменён в другом месте|Bu proje başka bir yerde değişti|此项目已在别处更改|此專案已在別處變更
Reload|Recharger|Ricarica|再読み込み|다시 불러오기|Recarregar|Перезагрузить|Yeniden yükle|重新加载|重新載入
Keep my copy|Garder ma copie|Mantieni la mia copia|自分のコピーを保持|내 사본 유지|Manter minha cópia|Оставить мою копию|Kopyamı koru|保留我的副本|保留我的副本
Unsaved changes found|Modifications non enregistrées trouvées|Modifiche non salvate trovate|未保存の変更が見つかりました|저장되지 않은 변경 사항 발견|Alterações não salvas encontradas|Найдены несохранённые изменения|Kaydedilmemiş değişiklikler bulundu|发现未保存的更改|發現未儲存的變更
Restore|Restaurer|Ripristina|復元|복원|Restaurar|Восстановить|Geri yükle|恢复|還原
Discard|Ignorer|Scarta|破棄|버리기|Descartar|Отбросить|Vazgeç|丢弃|捨棄
Saving|Enregistrement|Salvataggio|保存中|저장 중|Salvando|Сохранение|Kaydediliyor|保存中|儲存中
Parameters|Paramètres|Parametri|パラメーター|매개변수|Parâmetros|Параметры|Parametreler|参数|參數
Reset to default|Réinitialiser|Ripristina il valore|初期値に戻す|기본값으로 재설정|Redefinir para o padrão|Сбросить к исходному|Varsayılana sıfırla|重置为默认|重設為預設
Gamma|Gamma|Gamma|ガンマ|감마|Gama|Гамма|Gama|伽马|伽瑪
Lift|Relèvement|Sollevamento|リフト|리프트|Elevação|Подъём|Yükseltme|提升|提升
Temperature|Température|Temperatura|色温度|색온도|Temperatura|Температура|Sıcaklık|色温|色溫
Tint|Teinte|Tinta|ティント|틴트|Matiz|Оттенок|Ton|色调|色調
Shadows red|Ombres rouge|Ombre rosso|シャドウ 赤|섀도 빨강|Sombras vermelho|Тени красный|Gölgeler kırmızı|阴影 红|陰影 紅
Shadows green|Ombres vert|Ombre verde|シャドウ 緑|섀도 초록|Sombras verde|Тени зелёный|Gölgeler yeşil|阴影 绿|陰影 綠
Shadows blue|Ombres bleu|Ombre blu|シャドウ 青|섀도 파랑|Sombras azul|Тени синий|Gölgeler mavi|阴影 蓝|陰影 藍
Highlights red|Hautes lumières rouge|Luci rosso|ハイライト 赤|하이라이트 빨강|Realces vermelho|Света красный|Parlaklar kırmızı|高光 红|亮部 紅
Highlights green|Hautes lumières vert|Luci verde|ハイライト 緑|하이라이트 초록|Realces verde|Света зелёный|Parlaklar yeşil|高光 绿|亮部 綠
Highlights blue|Hautes lumières bleu|Luci blu|ハイライト 青|하이라이트 파랑|Realces azul|Света синий|Parlaklar mavi|高光 蓝|亮部 藍
Radius|Rayon|Raggio|半径|반경|Raio|Радиус|Yarıçap|半径|半徑
Size|Taille|Dimensione|サイズ|크기|Tamanho|Размер|Boyut|大小|大小
Levels|Niveaux|Livelli|レベル|레벨|Níveis|Уровни|Seviyeler|色阶|色階
Strength|Intensité|Intensità|強さ|강도|Intensidade|Сила|Güç|强度|強度
Select two or more pieces to rejoin|Sélectionnez au moins deux segments à réunir|Seleziona due o più parti da riunire|結合するには2つ以上の断片を選択|다시 결합하려면 두 개 이상 선택|Selecione duas ou mais partes para reunir|Выберите два или более фрагмента для соединения|Birleştirmek için iki veya daha fazla parça seçin|选择两个或更多片段进行合并|選擇兩個或更多片段進行合併
Pieces must sit on one track|Les segments doivent être sur une seule piste|Le parti devono stare su una sola traccia|断片は同じトラック上にある必要があります|조각이 한 트랙에 있어야 합니다|As partes devem estar em uma única trilha|Фрагменты должны быть на одной дорожке|Parçalar tek bir kanalda olmalı|片段必须位于同一轨道|片段必須位於同一軌道
The track is locked|La piste est verrouillée|La traccia è bloccata|トラックがロックされています|트랙이 잠겨 있습니다|A trilha está bloqueada|Дорожка заблокирована|Kanal kilitli|轨道已锁定|軌道已鎖定
Pieces must share the same media|Les segments doivent partager le même média|Le parti devono condividere lo stesso file|断片は同じメディアを共有する必要があります|조각이 같은 미디어를 공유해야 합니다|As partes devem compartilhar a mesma mídia|Фрагменты должны использовать один источник|Parçalar aynı medyayı paylaşmalı|片段必须共享同一媒体|片段必須共享同一媒體
Pieces must play at the same constant speed|Les segments doivent avoir la même vitesse constante|Le parti devono avere la stessa velocità costante|断片は同じ一定速度である必要があります|조각이 같은 일정 속도여야 합니다|As partes devem ter a mesma velocidade constante|Фрагменты должны идти с одной постоянной скоростью|Parçalar aynı sabit hızda olmalı|片段必须以相同恒定速度播放|片段必須以相同恆定速度播放
Pieces must touch on the timeline|Les segments doivent se toucher sur la timeline|Le parti devono toccarsi sulla timeline|断片はタイムライン上で接している必要があります|조각이 타임라인에서 맞닿아야 합니다|As partes devem se tocar na linha do tempo|Фрагменты должны соприкасаться на шкале|Parçalar zaman çizgisinde bitişik olmalı|片段必须在时间线上相接|片段必須在時間軸上相接
Pieces must continue the same source range|Les segments doivent prolonger la même plage source|Le parti devono continuare lo stesso intervallo di origine|断片は同じソース範囲の続きである必要があります|조각이 같은 소스 범위를 이어야 합니다|As partes devem continuar o mesmo intervalo de origem|Фрагменты должны продолжать один диапазон источника|Parçalar aynı kaynak aralığını sürdürmeli|片段必须延续同一源范围|片段必須延續同一來源範圍
Reverse|Inverser|Inverti|逆再生|역재생|Inverter|Реверс|Ters çevir|倒放|倒放
Preparing|Préparation|Preparazione|準備中|준비 중|Preparando|Подготовка|Hazırlanıyor|准备中|準備中
Could not prepare|Préparation impossible|Preparazione non riuscita|準備できませんでした|준비할 수 없습니다|Não foi possível preparar|Не удалось подготовить|Hazırlanamadı|无法准备|無法準備
Crop|Recadrer|Ritaglia|クロップ|자르기|Cortar|Кадрировать|Kırp|裁剪|裁切
Flip vertical|Miroir vertical|Capovolgi in verticale|上下反転|상하 반전|Inverter na vertical|Отразить по вертикали|Dikey çevir|垂直翻转|垂直翻轉
No detached sound belongs to this clip|Aucun son détaché n'appartient à ce clip|Nessun audio staccato appartiene a questa clip|このクリップに属する分離済み音声はありません|이 클립에 속한 분리된 소리가 없습니다|Nenhum som destacado pertence a este clipe|К этому клипу не относится отделённый звук|Bu klibe ait ayrılmış ses yok|没有属于此片段的分离音频|沒有屬於此片段的分離音訊
Add media|Ajouter des médias|Aggiungi media|メディアを追加|미디어 추가|Adicionar mídia|Добавить медиа|Medya ekle|添加媒体|新增媒體
Captions|Sous-titres|Sottotitoli|字幕|자막|Legendas|Субтитры|Altyazılar|字幕|字幕
Delete|Supprimer|Elimina|削除|삭제|Excluir|Удалить|Sil|删除|刪除
Duplicate|Dupliquer|Duplica|複製|복제|Duplicar|Дублировать|Çoğalt|复制|複製
Speed|Vitesse|Velocità|速度|속도|Velocidade|Скорость|Hız|速度|速度
Animate|Animer|Anima|アニメーション|애니메이션|Animar|Анимировать|Canlandır|动画|動畫
Filters|Filtres|Filtri|フィルター|필터|Filtros|Фильтры|Filtreler|滤镜|濾鏡
Remove background|Supprimer l'arrière-plan|Rimuovi sfondo|背景を削除|배경 제거|Remover fundo|Убрать фон|Arka planı kaldır|移除背景|移除背景
Freeze|Figer|Blocca|フリーズ|고정|Congelar|Стоп-кадр|Dondur|定格|定格
Edit text|Modifier le texte|Modifica testo|テキストを編集|텍스트 편집|Editar texto|Изменить текст|Metni düzenle|编辑文本|編輯文字
Style|Style|Stile|スタイル|스타일|Estilo|Стиль|Stil|样式|樣式
Fade|Fondu|Dissolvenza|フェード|페이드|Fade|Затухание|Geçiş|淡化|淡化
Voice effects|Effets de voix|Effetti voce|音声エフェクト|음성 효과|Efeitos de voz|Голосовые эффекты|Ses efektleri|语音效果|語音效果
Place the playhead inside the clip|Placez la tête de lecture dans le clip|Posiziona l'indicatore dentro la clip|再生ヘッドをクリップ内に置いてください|재생 헤드를 클립 안에 두세요|Coloque o cursor dentro do clipe|Поместите курсор внутрь клипа|Oynatma kafasını klibin içine koyun|将播放头放在片段内|將播放頭放在片段內
Video clips only|Clips vidéo uniquement|Solo clip video|ビデオクリップのみ|비디오 클립만|Apenas clipes de vídeo|Только видеоклипы|Yalnızca video klipler|仅限视频片段|僅限視訊片段
Weight|Graisse|Spessore|太さ|굵기|Espessura|Насыщенность|Kalınlık|字重|字重
Italic|Italique|Corsivo|斜体|기울임꼴|Itálico|Курсив|İtalik|斜体|斜體
Outline|Contour|Contorno|縁取り|윤곽선|Contorno|Обводка|Anahat|描边|描邊
Shadow|Ombre|Ombra|影|그림자|Sombra|Тень|Gölge|阴影|陰影
Shadow offset|Décalage de l'ombre|Scostamento ombra|影のオフセット|그림자 오프셋|Deslocamento da sombra|Смещение тени|Gölge kayması|阴影偏移|陰影偏移
Background plate|Fond|Sfondo|背景プレート|배경 판|Placa de fundo|Подложка|Arka plan|背景板|背景板
Plate padding and radius|Marge et rayon du fond|Spaziatura e raggio dello sfondo|背景の余白と角丸|배경 여백과 반경|Espaçamento e raio da placa|Отступ и радиус подложки|Dolgu ve yarıçap|背景内边距与圆角|背景內距與圓角
Line height|Interligne|Interlinea|行の高さ|줄 높이|Altura da linha|Межстрочный интервал|Satır yüksekliği|行高|行高
Letter spacing|Interlettrage|Spaziatura lettere|字間|자간|Espaçamento entre letras|Межбуквенный интервал|Harf aralığı|字间距|字間距
Wrap width|Largeur de retour|Larghezza di a capo|折り返し幅|줄바꿈 폭|Largura de quebra|Ширина переноса|Kaydırma genişliği|换行宽度|換行寬度
Text opacity|Opacité du texte|Opacità del testo|文字の不透明度|텍스트 불투명도|Opacidade do texto|Непрозрачность текста|Metin saydamlığı|文字不透明度|文字不透明度
Title styles|Styles de titre|Stili di titolo|タイトルスタイル|제목 스타일|Estilos de título|Стили заголовка|Başlık stilleri|标题样式|標題樣式
Style saved for new titles and captions|Style enregistré pour les nouveaux titres et sous-titres|Stile salvato per nuovi titoli e sottotitoli|新しいタイトルと字幕にスタイルを保存しました|새 제목과 자막에 스타일을 저장했습니다|Estilo salvo para novos títulos e legendas|Стиль сохранён для новых заголовков и субтитров|Yeni başlıklar ve altyazılar için stil kaydedildi|已为新标题和字幕保存样式|已為新標題和字幕儲存樣式
Model|Modèle|Modello|モデル|모델|Modelo|Модель|Model|模型|模型
Tiny (fastest)|Tiny (le plus rapide)|Tiny (il più veloce)|Tiny（最速）|Tiny(가장 빠름)|Tiny (mais rápido)|Tiny (самая быстрая)|Tiny (en hızlı)|Tiny（最快）|Tiny（最快）
Small (most accurate)|Small (le plus précis)|Small (il più preciso)|Small（最も正確）|Small(가장 정확)|Small (mais preciso)|Small (самая точная)|Small (en doğru)|Small（最准确）|Small（最準確）
Words|Mots|Parole|単語数|단어 수|Palavras|Слова|Kelime|字数|字數
Placement|Position|Posizione|配置|배치|Posição|Расположение|Yerleşim|位置|位置
Centre|Centre|Centro|中央|가운데|Centro|По центру|Orta|居中|置中
Bottom|Bas|In basso|下|아래|Abaixo|Внизу|Alt|底部|底部
Cancelled|Annulé|Annullato|キャンセルしました|취소됨|Cancelado|Отменено|İptal edildi|已取消|已取消
Or type caption lines, one per line|Ou saisissez les sous-titres, un par ligne|Oppure digita i sottotitoli, uno per riga|または字幕を1行ずつ入力|또는 자막을 한 줄씩 입력|Ou digite legendas, uma por linha|Или введите субтитры по строке|Ya da altyazıları satır satır yazın|或逐行输入字幕|或逐行輸入字幕
One caption per line|Un sous-titre par ligne|Un sottotitolo per riga|1行に1つの字幕|한 줄에 자막 하나|Uma legenda por linha|По одному субтитру в строке|Satır başına bir altyazı|每行一条字幕|每行一條字幕
Add typed captions|Ajouter les sous-titres saisis|Aggiungi i sottotitoli digitati|入力した字幕を追加|입력한 자막 추가|Adicionar legendas digitadas|Добавить введённые субтитры|Yazılan altyazıları ekle|添加输入的字幕|新增輸入的字幕
Type at least one line|Saisissez au moins une ligne|Digita almeno una riga|1行以上入力してください|한 줄 이상 입력하세요|Digite pelo menos uma linha|Введите хотя бы одну строку|En az bir satır yazın|请至少输入一行|請至少輸入一行
Remove background|Supprimer l'arrière-plan|Rimuovi sfondo|背景を削除|배경 제거|Remover fundo|Убрать фон|Arka planı kaldır|移除背景|移除背景
Mode|Mode|Modalità|モード|모드|Modo|Режим|Mod|模式|模式
Automatic|Automatique|Automatico|自動|자동|Automático|Автоматически|Otomatik|自动|自動
Brush|Pinceau|Pennello|ブラシ|브러시|Pincel|Кисть|Fırça|画笔|筆刷
Chroma key|Incrustation|Chroma key|クロマキー|크로마 키|Chroma key|Хромакей|Kroma anahtarı|色度键|色度鍵
Feather|Contour progressif|Sfumatura|ぼかし|페더|Suavização|Растушёвка|Yumuşatma|羽化|羽化
Brush size|Taille du pinceau|Dimensione pennello|ブラシサイズ|브러시 크기|Tamanho do pincel|Размер кисти|Fırça boyutu|画笔大小|筆刷大小
Ready|Prêt|Pronto|準備完了|준비됨|Pronto|Готово|Hazır|就绪|就緒
Not available in this layout|Indisponible dans cette disposition|Non disponibile in questo layout|このレイアウトでは利用できません|이 레이아웃에서는 사용할 수 없습니다|Indisponível neste layout|Недоступно в этом макете|Bu düzende kullanılamaz|此布局中不可用|此配置中不可用`;
export const PHRASES: Record<string, Record<string, string>> = Object.fromEntries(codes.map(c => [c, {}]));
for (const row of rows.split("\n")) {
  const [source, ...values] = row.split("|");
  if (values.length !== codes.length) throw new Error(`Invalid language row: ${source}`);
  codes.forEach((code, i) => PHRASES[code][source] = values[i]);
}
export function languagePack(english: Record<string, string>): Record<string, Record<string, string>> {
  return Object.fromEntries(codes.map(code => [code, Object.fromEntries(Object.entries(english).map(([key, value]) => [key, PHRASES[code][value] ?? value]))]));
}
