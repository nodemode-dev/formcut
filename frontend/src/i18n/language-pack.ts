const codes = ["fr", "it", "ja", "ko", "pt-BR", "ru", "tr", "zh-Hans", "zh-Hant"];
const rows = `Move earlier|Déplacer plus tôt|Sposta prima|前へ移動|앞으로 이동|Mover para antes|Переместить раньше|Öne taşı|前移|前移
Turn off|Désactiver|Disattiva|オフにする|끄기|Desativar|Выключить|Kapat|关闭|關閉
Turn on|Activer|Attiva|オンにする|켜기|Ativar|Включить|Aç|开启|開啟
Encodes as {codec} with {encoder}|Encode en {codec} avec {encoder}|Codifica in {codec} con {encoder}|{encoder} で {codec} にエンコード|{encoder}(으)로 {codec} 인코딩|Codifica como {codec} com {encoder}|Кодирование в {codec} через {encoder}|{encoder} ile {codec} olarak kodlar|使用 {encoder} 编码为 {codec}|使用 {encoder} 編碼為 {codec}
No H.264 or HEVC encoder works on this machine, so MP4 uses MPEG-4 Part 2, which Instagram and some players refuse.|Aucun encodeur H.264 ou HEVC ne fonctionne sur cette machine : le MP4 utilise donc MPEG-4 Part 2, que refusent Instagram et certains lecteurs.|Su questo computer non funziona alcun encoder H.264 o HEVC, quindi l'MP4 usa MPEG-4 Part 2, che Instagram e alcuni lettori rifiutano.|このマシンでは H.264 と HEVC のエンコーダーが使えないため、MP4 は MPEG-4 Part 2 になります。Instagram や一部のプレーヤーでは受け付けられません。|이 컴퓨터에서 작동하는 H.264 또는 HEVC 인코더가 없어 MP4가 MPEG-4 Part 2를 사용합니다. Instagram과 일부 플레이어는 이를 거부합니다.|Nenhum codificador H.264 ou HEVC funciona nesta máquina, então o MP4 usa MPEG-4 Part 2, que o Instagram e alguns players recusam.|На этом компьютере не работает ни один кодировщик H.264 или HEVC, поэтому MP4 использует MPEG-4 Part 2, который Instagram и некоторые плееры не принимают.|Bu makinede çalışan bir H.264 veya HEVC kodlayıcı yok, bu yüzden MP4 MPEG-4 Part 2 kullanıyor; Instagram ve bazı oynatıcılar bunu reddeder.|这台机器上没有可用的 H.264 或 HEVC 编码器，因此 MP4 使用 MPEG-4 Part 2，Instagram 和部分播放器会拒绝它。|這台機器上沒有可用的 H.264 或 HEVC 編碼器，因此 MP4 使用 MPEG-4 Part 2，Instagram 和部分播放器會拒絕它。
Phones and other computers|Téléphones et autres ordinateurs|Telefoni e altri computer|スマートフォンとほかのコンピューター|휴대폰 및 다른 컴퓨터|Celulares e outros computadores|Телефоны и другие компьютеры|Telefonlar ve diğer bilgisayarlar|手机和其他电脑|手機和其他電腦
Use formcut from a phone or another computer on this network|Utiliser formcut depuis un téléphone ou un autre ordinateur de ce réseau|Usa formcut da un telefono o da un altro computer di questa rete|このネットワーク上のスマートフォンやほかのコンピューターから formcut を使う|이 네트워크의 휴대폰이나 다른 컴퓨터에서 formcut 사용|Usar o formcut em um celular ou outro computador desta rede|Работать в formcut с телефона или другого компьютера в этой сети|formcut'ı bu ağdaki bir telefondan veya başka bir bilgisayardan kullanın|在此网络中的手机或其他电脑上使用 formcut|在此網路中的手機或其他電腦上使用 formcut
Allow paired devices on this network|Autoriser les appareils associés sur ce réseau|Consenti i dispositivi associati su questa rete|このネットワーク上のペアリング済みデバイスを許可|이 네트워크에서 페어링된 기기 허용|Permitir dispositivos pareados nesta rede|Разрешить сопряжённые устройства в этой сети|Bu ağdaki eşlenmiş cihazlara izin ver|允许此网络中已配对的设备|允許此網路中已配對的裝置
On the phone or computer, open:|Sur le téléphone ou l'ordinateur, ouvrez :|Sul telefono o sul computer, apri:|スマートフォンまたはコンピューターで次を開きます：|휴대폰이나 컴퓨터에서 다음 주소를 여세요:|No celular ou computador, abra:|На телефоне или компьютере откройте:|Telefonda veya bilgisayarda şunu açın:|在手机或电脑上打开：|在手機或電腦上開啟：
Pair a device|Associer un appareil|Associa un dispositivo|デバイスをペアリング|기기 페어링|Parear um dispositivo|Сопрячь устройство|Cihaz eşle|配对设备|配對裝置
Enter this code on the device: {code}|Saisissez ce code sur l'appareil : {code}|Inserisci questo codice sul dispositivo: {code}|デバイスでこのコードを入力：{code}|기기에서 이 코드를 입력하세요: {code}|Digite este código no dispositivo: {code}|Введите этот код на устройстве: {code}|Bu kodu cihaza girin: {code}|在设备上输入此代码：{code}|在裝置上輸入此代碼：{code}
Anyone on this network can open the pairing page, but only a device with a fresh code can pair, and each code works once.|Tout le monde sur ce réseau peut ouvrir la page d'association, mais seul un appareil disposant d'un code récent peut s'associer, et chaque code ne sert qu'une fois.|Chiunque su questa rete può aprire la pagina di associazione, ma solo un dispositivo con un codice recente può associarsi, e ogni codice vale una volta.|このネットワーク上の誰でもペアリングページを開けますが、ペアリングできるのは新しいコードを持つデバイスだけで、各コードは 1 回しか使えません。|이 네트워크의 누구나 페어링 페이지를 열 수 있지만, 새 코드가 있는 기기만 페어링할 수 있고 각 코드는 한 번만 쓸 수 있습니다.|Qualquer pessoa nesta rede pode abrir a página de pareamento, mas só um dispositivo com um código recente consegue parear, e cada código vale uma vez.|Страницу сопряжения может открыть любой в этой сети, но сопрячь устройство можно только со свежим кодом, и каждый код действует один раз.|Bu ağdaki herkes eşleme sayfasını açabilir, ancak yalnızca yeni bir koda sahip cihaz eşlenebilir ve her kod bir kez çalışır.|此网络中的任何人都能打开配对页面，但只有持有新代码的设备才能配对，且每个代码只能使用一次。|此網路中的任何人都能開啟配對頁面，但只有持有新代碼的裝置才能配對，且每個代碼只能使用一次。
No paired devices yet|Aucun appareil associé pour l'instant|Ancora nessun dispositivo associato|ペアリング済みのデバイスはまだありません|아직 페어링된 기기가 없습니다|Nenhum dispositivo pareado ainda|Сопряжённых устройств пока нет|Henüz eşlenmiş cihaz yok|尚无已配对的设备|尚無已配對的裝置
No network address found|Aucune adresse réseau trouvée|Nessun indirizzo di rete trovato|ネットワークアドレスが見つかりません|네트워크 주소를 찾을 수 없습니다|Nenhum endereço de rede encontrado|Сетевой адрес не найден|Ağ adresi bulunamadı|未找到网络地址|找不到網路位址
Cloud storage|Stockage cloud|Archiviazione cloud|クラウドストレージ|클라우드 저장소|Armazenamento em nuvem|Облачное хранилище|Bulut depolama|云存储|雲端儲存空間
From the cloud|Depuis le cloud|Dal cloud|クラウドから|클라우드에서|Da nuvem|Из облака|Buluttan|从云端|從雲端
Set up {service} in Settings first|Configurez d'abord {service} dans les réglages|Configura prima {service} nelle impostazioni|先に設定で {service} を設定してください|먼저 설정에서 {service}을(를) 설정하세요|Configure o {service} nas configurações primeiro|Сначала настройте {service} в настройках|Önce Ayarlar'da {service} hizmetini kurun|请先在设置中配置 {service}|請先在設定中設定 {service}
Back|Retour|Indietro|戻る|뒤로|Voltar|Назад|Geri|返回|返回
This folder is empty|Ce dossier est vide|Questa cartella è vuota|このフォルダーは空です|이 폴더는 비어 있습니다|Esta pasta está vazia|Эта папка пуста|Bu klasör boş|此文件夹为空|此資料夾是空的
Load more|Charger plus|Carica altro|さらに読み込む|더 불러오기|Carregar mais|Загрузить ещё|Daha fazla yükle|加载更多|載入更多
Fetching the file|Récupération du fichier|Recupero del file|ファイルを取得中|파일을 가져오는 중|Buscando o arquivo|Получение файла|Dosya alınıyor|正在获取文件|正在取得檔案
Save to the cloud|Enregistrer dans le cloud|Salva nel cloud|クラウドに保存|클라우드에 저장|Salvar na nuvem|Сохранить в облако|Buluta kaydet|保存到云端|儲存到雲端
Upload|Téléverser|Carica|アップロード|업로드|Enviar|Загрузить|Yükle|上传|上傳
Uploading|Téléversement en cours|Caricamento in corso|アップロード中|업로드 중|Enviando|Загрузка|Yükleniyor|正在上传|正在上傳
Saved to {service}: {name}|Enregistré dans {service} : {name}|Salvato in {service}: {name}|{service} に保存しました：{name}|{service}에 저장됨: {name}|Salvo no {service}: {name}|Сохранено в {service}: {name}|{service} hizmetine kaydedildi: {name}|已保存到 {service}：{name}|已儲存到 {service}：{name}
Save the last export to the cloud|Enregistrer le dernier export dans le cloud|Salva l'ultima esportazione nel cloud|最後の書き出しをクラウドに保存|마지막 내보내기를 클라우드에 저장|Salvar a última exportação na nuvem|Сохранить последний экспорт в облако|Son dışa aktarımı buluta kaydet|将最近一次导出保存到云端|將最近一次匯出儲存到雲端
Not connected|Non connecté|Non collegato|未接続|연결되지 않음|Não conectado|Не подключено|Bağlı değil|未连接|未連結
Import from and save to Google Drive|Importer depuis Google Drive et y enregistrer|Importa da Google Drive e salva su Google Drive|Google Drive から読み込み、Google Drive に保存|Google Drive에서 가져오고 Google Drive에 저장|Importar do Google Drive e salvar nele|Импорт из Google Drive и сохранение в него|Google Drive'dan içe aktar ve oraya kaydet|从 Google Drive 导入并保存到 Google Drive|從 Google Drive 匯入並儲存到 Google Drive
Import from and save to Dropbox|Importer depuis Dropbox et y enregistrer|Importa da Dropbox e salva su Dropbox|Dropbox から読み込み、Dropbox に保存|Dropbox에서 가져오고 Dropbox에 저장|Importar do Dropbox e salvar nele|Импорт из Dropbox и сохранение в него|Dropbox'tan içe aktar ve oraya kaydet|从 Dropbox 导入并保存到 Dropbox|從 Dropbox 匯入並儲存到 Dropbox
Client ID|ID client|ID client|クライアント ID|클라이언트 ID|ID do cliente|Идентификатор клиента|İstemci kimliği|客户端 ID|用戶端 ID
Client secret|Secret client|Segreto client|クライアントシークレット|클라이언트 시크릿|Segredo do cliente|Секрет клиента|İstemci gizli anahtarı|客户端密钥|用戶端密鑰
App key|Clé d'app|Chiave dell'app|アプリキー|앱 키|Chave do app|Ключ приложения|Uygulama anahtarı|应用密钥|應用程式金鑰
Browse all of Drive (read-only access, which Google reviews before public use)|Parcourir tout Drive (accès en lecture seule, que Google examine avant une utilisation publique)|Sfoglia tutto Drive (accesso in sola lettura, che Google verifica prima dell'uso pubblico)|Drive 全体を閲覧（読み取り専用。公開前に Google の審査が必要）|Drive 전체 탐색(읽기 전용 액세스, 공개 사용 전 Google 검토 필요)|Navegar por todo o Drive (acesso somente leitura, que o Google analisa antes do uso público)|Просматривать весь Drive (доступ только для чтения, который Google проверяет перед публичным использованием)|Tüm Drive'a göz at (salt okunur erişim; herkese açık kullanımdan önce Google tarafından incelenir)|浏览整个 Drive（只读权限，公开使用前需经 Google 审核）|瀏覽整個 Drive（唯讀權限，公開使用前需經 Google 審核）
Without it, formcut sees only the files it saved to Drive.|Sans cela, formcut ne voit que les fichiers qu'il a enregistrés dans Drive.|Senza, formcut vede solo i file che ha salvato su Drive.|オフの場合、formcut は自分が Drive に保存したファイルだけを表示します。|끄면 formcut은 자신이 Drive에 저장한 파일만 볼 수 있습니다.|Sem isso, o formcut vê só os arquivos que salvou no Drive.|Без этого formcut видит только файлы, которые сам сохранил в Drive.|Bu olmadan formcut yalnızca Drive'a kendi kaydettiği dosyaları görür.|不开启时，formcut 只能看到它自己保存到 Drive 的文件。|不開啟時，formcut 只能看到它自己儲存到 Drive 的檔案。
Paste the code Dropbox shows|Collez le code affiché par Dropbox|Incolla il codice mostrato da Dropbox|Dropbox に表示されたコードを貼り付け|Dropbox에 표시된 코드를 붙여넣기|Cole o código que o Dropbox mostra|Вставьте код, который показывает Dropbox|Dropbox'ın gösterdiği kodu yapıştırın|粘贴 Dropbox 显示的代码|貼上 Dropbox 顯示的代碼
Finish|Terminer|Fine|完了|완료|Concluir|Готово|Bitir|完成|完成
Post to Instagram…|Publier sur Instagram…|Pubblica su Instagram…|Instagram に投稿…|Instagram에 게시…|Postar no Instagram…|Опубликовать в Instagram…|Instagram'da paylaş…|发布到 Instagram…|發布到 Instagram…
Post to Instagram|Publier sur Instagram|Pubblica su Instagram|Instagram に投稿|Instagram에 게시|Postar no Instagram|Опубликовать в Instagram|Instagram'da paylaş|发布到 Instagram|發布到 Instagram
Connect Instagram in Settings first|Connectez d'abord Instagram dans les réglages|Collega prima Instagram nelle impostazioni|先に設定で Instagram に接続してください|먼저 설정에서 Instagram을 연결하세요|Conecte o Instagram nas configurações primeiro|Сначала подключите Instagram в настройках|Önce Ayarlar'da Instagram'ı bağlayın|请先在设置中连接 Instagram|請先在設定中連結 Instagram
Posting as @{name}|Publication en tant que @{name}|Pubblicazione come @{name}|@{name} として投稿|@{name}(으)로 게시|Postando como @{name}|Публикация от имени @{name}|@{name} olarak paylaşılıyor|以 @{name} 的身份发布|以 @{name} 的身分發布
Also share to the main feed|Partager aussi dans le fil principal|Condividi anche nel feed principale|メインフィードにもシェア|메인 피드에도 공유|Compartilhar também no feed principal|Также показать в основной ленте|Ana akışta da paylaş|同时分享到主页动态|同時分享到主頁動態
Instagram Reels need H.264 or HEVC video. Export with an H.264 encoder first.|Les Reels Instagram exigent une vidéo H.264 ou HEVC. Exportez d'abord avec un encodeur H.264.|I Reel di Instagram richiedono video H.264 o HEVC. Esporta prima con un codificatore H.264.|Instagram のリールには H.264 または HEVC の動画が必要です。先に H.264 エンコーダーで書き出してください。|Instagram 릴스에는 H.264 또는 HEVC 동영상이 필요합니다. 먼저 H.264 인코더로 내보내세요.|Os Reels do Instagram exigem vídeo H.264 ou HEVC. Exporte primeiro com um codificador H.264.|Для Reels в Instagram нужно видео H.264 или HEVC. Сначала экспортируйте с кодировщиком H.264.|Instagram Reels için H.264 veya HEVC video gerekir. Önce bir H.264 kodlayıcıyla dışa aktarın.|Instagram Reels 需要 H.264 或 HEVC 视频。请先使用 H.264 编码器导出。|Instagram Reels 需要 H.264 或 HEVC 影片。請先使用 H.264 編碼器匯出。
Sending to Instagram|Envoi vers Instagram|Invio a Instagram|Instagram に送信中|Instagram으로 보내는 중|Enviando para o Instagram|Отправка в Instagram|Instagram'a gönderiliyor|正在发送到 Instagram|正在傳送到 Instagram
Published on Instagram|Publié sur Instagram|Pubblicato su Instagram|Instagram に公開しました|Instagram에 게시됨|Publicado no Instagram|Опубликовано в Instagram|Instagram'da yayınlandı|已发布到 Instagram|已發布到 Instagram
Post the last export to Instagram|Publier le dernier export sur Instagram|Pubblica l'ultima esportazione su Instagram|最後の書き出しを Instagram に投稿|마지막 내보내기를 Instagram에 게시|Postar a última exportação no Instagram|Опубликовать последний экспорт в Instagram|Son dışa aktarımı Instagram'da paylaş|将最近一次导出发布到 Instagram|將最近一次匯出發布到 Instagram
Posting Reels to Instagram|Publication de Reels sur Instagram|Pubblicazione di Reel su Instagram|Instagram へのリール投稿|Instagram에 릴스 게시|Postagem de Reels no Instagram|Публикация Reels в Instagram|Instagram'da Reels paylaşımı|将 Reels 发布到 Instagram|將 Reels 發布到 Instagram
Access token from your Meta app|Jeton d'accès de votre app Meta|Token di accesso della tua app Meta|Meta アプリのアクセストークン|Meta 앱의 액세스 토큰|Token de acesso do seu app da Meta|Токен доступа из вашего приложения Meta|Meta uygulamanızdan erişim belirteci|来自你的 Meta 应用的访问令牌|來自你的 Meta App 的存取權杖
Connect|Connecter|Collega|接続|연결|Conectar|Подключить|Bağla|连接|連結
Needs instagram_content_publish. formcut finds the Instagram professional account linked to your Facebook Page.|Nécessite instagram_content_publish. formcut trouve le compte Instagram professionnel lié à votre Page Facebook.|Richiede instagram_content_publish. formcut trova l'account Instagram professionale collegato alla tua Pagina Facebook.|instagram_content_publish が必要です。formcut が Facebook ページにリンクされた Instagram プロアカウントを見つけます。|instagram_content_publish 권한이 필요합니다. formcut이 Facebook 페이지에 연결된 Instagram 프로페셔널 계정을 찾습니다.|Requer instagram_content_publish. O formcut encontra a conta profissional do Instagram vinculada à sua Página do Facebook.|Нужно разрешение instagram_content_publish. formcut найдёт профессиональный аккаунт Instagram, связанный с вашей страницей Facebook.|instagram_content_publish izni gerekir. formcut, Facebook Sayfanıza bağlı Instagram profesyonel hesabını bulur.|需要 instagram_content_publish 权限。formcut 会找到与你的 Facebook 公共主页关联的 Instagram 专业账号。|需要 instagram_content_publish 權限。formcut 會找到與你的 Facebook 粉絲專頁連結的 Instagram 專業帳號。
Post to TikTok…|Publier sur TikTok…|Pubblica su TikTok…|TikTok に投稿…|TikTok에 게시…|Postar no TikTok…|Опубликовать в TikTok…|TikTok'ta paylaş…|发布到 TikTok…|發布到 TikTok…
Post to TikTok|Publier sur TikTok|Pubblica su TikTok|TikTok に投稿|TikTok에 게시|Postar no TikTok|Опубликовать в TikTok|TikTok'ta paylaş|发布到 TikTok|發布到 TikTok
Set up TikTok in Settings first|Configurez d'abord TikTok dans les réglages|Configura prima TikTok nelle impostazioni|先に設定で TikTok を設定してください|먼저 설정에서 TikTok을 설정하세요|Configure o TikTok nas configurações primeiro|Сначала настройте TikTok в настройках|Önce Ayarlar'da TikTok'u kurun|请先在设置中配置 TikTok|請先在設定中設定 TikTok
Connect TikTok|Connecter TikTok|Collega TikTok|TikTok に接続|TikTok 연결|Conectar o TikTok|Подключить TikTok|TikTok'u bağla|连接 TikTok|連結 TikTok
Finish signing in in your browser. If it did not open, use this link:|Terminez la connexion dans votre navigateur. S'il ne s'est pas ouvert, utilisez ce lien :|Completa l'accesso nel browser. Se non si è aperto, usa questo link:|ブラウザでサインインを完了してください。開かない場合は次のリンクを使用してください：|브라우저에서 로그인을 완료하세요. 열리지 않았다면 이 링크를 사용하세요:|Termine de entrar no navegador. Se ele não abriu, use este link:|Завершите вход в браузере. Если он не открылся, используйте эту ссылку:|Tarayıcınızda oturum açmayı tamamlayın. Açılmadıysa bu bağlantıyı kullanın:|请在浏览器中完成登录。如果浏览器没有打开，请使用此链接：|請在瀏覽器中完成登入。如果瀏覽器沒有開啟，請使用此連結：
Send as a draft|Envoyer en brouillon|Invia come bozza|下書きとして送信|초안으로 보내기|Enviar como rascunho|Отправить как черновик|Taslak olarak gönder|作为草稿发送|以草稿傳送
It arrives in your TikTok inbox, to finish and post in the app.|Il arrive dans votre boîte de réception TikTok, pour le finaliser et le publier dans l'app.|Arriva nella tua casella TikTok, da completare e pubblicare nell'app.|TikTok の受信トレイに届くので、アプリで仕上げて投稿します。|TikTok 받은편지함으로 전송되며, 앱에서 마무리해 게시합니다.|Ele chega à sua caixa de entrada do TikTok para você finalizar e postar no app.|Он придёт во входящие TikTok, где его можно доработать и опубликовать в приложении.|TikTok gelen kutunuza gelir; uygulamada tamamlayıp paylaşırsınız.|它会进入你的 TikTok 收件箱，在应用中完成并发布。|它會進入你的 TikTok 收件匣，在 App 中完成並發布。
Post directly|Publier directement|Pubblica direttamente|直接投稿|바로 게시|Postar diretamente|Опубликовать сразу|Doğrudan paylaş|直接发布|直接發布
Until this app passes TikTok's review, TikTok keeps direct posts private.|Tant que cette app n'a pas passé l'examen de TikTok, TikTok garde les publications directes privées.|Finché questa app non supera la revisione di TikTok, TikTok mantiene privati i post diretti.|このアプリが TikTok の審査を通過するまで、直接投稿は非公開になります。|이 앱이 TikTok 심사를 통과할 때까지 TikTok은 바로 게시한 동영상을 비공개로 유지합니다.|Até este app passar na revisão do TikTok, o TikTok mantém as postagens diretas privadas.|Пока приложение не пройдёт проверку TikTok, TikTok оставляет прямые публикации приватными.|Bu uygulama TikTok incelemesinden geçene kadar TikTok doğrudan paylaşımları gizli tutar.|在此应用通过 TikTok 审核之前，TikTok 会将直接发布的内容设为私密。|在此 App 通過 TikTok 審核之前，TikTok 會將直接發布的內容設為私人。
Caption|Légende|Didascalia|キャプション|캡션|Legenda|Подпись|Açıklama|描述|描述
Who can watch|Qui peut regarder|Chi può guardare|視聴できる人|시청 가능 대상|Quem pode assistir|Кто может смотреть|Kimler izleyebilir|谁可以观看|誰可以觀看
Everyone|Tout le monde|Tutti|全員|모든 사람|Todos|Все|Herkes|所有人|所有人
Friends|Amis|Amici|友達|친구|Amigos|Друзья|Arkadaşlar|好友|好友
Followers|Abonnés|Follower|フォロワー|팔로워|Seguidores|Подписчики|Takipçiler|粉丝|粉絲
Only me|Moi uniquement|Solo io|自分のみ|나만 보기|Só eu|Только я|Yalnızca ben|仅自己|僅限自己
Allow comments|Autoriser les commentaires|Consenti commenti|コメントを許可|댓글 허용|Permitir comentários|Разрешить комментарии|Yorumlara izin ver|允许评论|允許留言
Allow Duet|Autoriser le Duo|Consenti Duetto|デュエットを許可|듀엣 허용|Permitir Dueto|Разрешить дуэт|Düete izin ver|允许合拍|允許合拍
Allow Stitch|Autoriser le Stitch|Consenti Stitch|Stitch を許可|이어찍기 허용|Permitir Costura|Разрешить сшивку|Stitch'e izin ver|允许拼接|允許拼接
By posting, you agree to TikTok's Music Usage Confirmation.|En publiant, vous acceptez la Confirmation d'utilisation de la musique de TikTok.|Pubblicando, accetti la Conferma di utilizzo della musica di TikTok.|投稿すると、TikTok の音楽使用確認に同意したことになります。|게시하면 TikTok의 음악 사용 확인에 동의하게 됩니다.|Ao postar, você concorda com a Confirmação de Uso de Música do TikTok.|Публикуя, вы соглашаетесь с подтверждением использования музыки TikTok.|Paylaşarak TikTok'un Müzik Kullanım Onayı'nı kabul etmiş olursunuz.|发布即表示你同意 TikTok 的音乐使用确认。|發布即表示你同意 TikTok 的音樂使用確認。
Posting as {name}|Publication en tant que {name}|Pubblicazione come {name}|{name} として投稿|{name}(으)로 게시|Postando como {name}|Публикация от имени {name}|{name} olarak paylaşılıyor|以 {name} 的身份发布|以 {name} 的身分發布
Send|Envoyer|Invia|送信|보내기|Enviar|Отправить|Gönder|发送|傳送
Sending to TikTok|Envoi vers TikTok|Invio a TikTok|TikTok に送信中|TikTok으로 보내는 중|Enviando para o TikTok|Отправка в TikTok|TikTok'a gönderiliyor|正在发送到 TikTok|正在傳送到 TikTok
In your TikTok inbox: open TikTok to finish the post|Dans votre boîte de réception TikTok : ouvrez TikTok pour finaliser la publication|Nella tua casella TikTok: apri TikTok per completare il post|TikTok の受信トレイに届きました。TikTok を開いて投稿を完了してください|TikTok 받은편지함에 도착했습니다. TikTok을 열어 게시를 완료하세요|Na sua caixa de entrada do TikTok: abra o TikTok para finalizar a postagem|Во входящих TikTok: откройте TikTok, чтобы завершить публикацию|TikTok gelen kutunuzda: paylaşımı tamamlamak için TikTok'u açın|已进入你的 TikTok 收件箱：打开 TikTok 完成发布|已進入你的 TikTok 收件匣：開啟 TikTok 完成發布
Posted to TikTok|Publié sur TikTok|Pubblicato su TikTok|TikTok に投稿しました|TikTok에 게시됨|Postado no TikTok|Опубликовано в TikTok|TikTok'ta paylaşıldı|已发布到 TikTok|已發布到 TikTok
Post the last export to TikTok|Publier le dernier export sur TikTok|Pubblica l'ultima esportazione su TikTok|最後の書き出しを TikTok に投稿|마지막 내보내기를 TikTok에 게시|Postar a última exportação no TikTok|Опубликовать последний экспорт в TikTok|Son dışa aktarımı TikTok'ta paylaş|将最近一次导出发布到 TikTok|將最近一次匯出發布到 TikTok
Posting to TikTok|Publication sur TikTok|Pubblicazione su TikTok|TikTok への投稿|TikTok에 게시|Postagem no TikTok|Публикация в TikTok|TikTok'ta paylaşım|发布到 TikTok|發布到 TikTok
Client key|Clé client|Chiave client|クライアントキー|클라이언트 키|Chave do cliente|Ключ клиента|İstemci anahtarı|客户端 ID|用戶端 ID
Client secret, for your own TikTok app|Secret client, pour votre propre app TikTok|Segreto client, per la tua app TikTok|クライアントシークレット（自分の TikTok アプリ用）|클라이언트 시크릿(내 TikTok 앱용)|Segredo do cliente, para o seu próprio app do TikTok|Секрет клиента для вашего приложения TikTok|İstemci gizli anahtarı, kendi TikTok uygulamanız için|客户端密钥（用于你自己的 TikTok 应用）|用戶端密鑰（用於你自己的 TikTok App）
Token relay address, if you host one|Adresse du relais de jetons, si vous en hébergez un|Indirizzo del relay dei token, se ne ospiti uno|トークンリレーのアドレス（ホストしている場合）|토큰 릴레이 주소(직접 호스팅하는 경우)|Endereço do relay de tokens, se você hospedar um|Адрес ретранслятора токенов, если вы его размещаете|Barındırıyorsanız token aktarıcısının adresi|令牌中继地址（如果你自行托管）|權杖中繼位址（如果你自行託管）
Register this redirect in the TikTok app:|Enregistrez cette redirection dans l'app TikTok :|Registra questo reindirizzamento nell'app TikTok:|TikTok アプリにこのリダイレクトを登録してください：|TikTok 앱에 이 리디렉션을 등록하세요:|Registre este redirecionamento no app do TikTok:|Зарегистрируйте этот адрес перенаправления в приложении TikTok:|Bu yönlendirmeyi TikTok uygulamasına kaydedin:|请在 TikTok 应用中登记此重定向地址：|請在 TikTok App 中登記此重新導向位址：
Not set up|Non configuré|Non configurato|未設定|설정 안 됨|Não configurado|Не настроено|Kurulmadı|未设置|未設定
Ready to connect|Prêt à se connecter|Pronto per il collegamento|接続できます|연결 준비됨|Pronto para conectar|Готово к подключению|Bağlanmaya hazır|可以连接|可以連結
Disconnect|Déconnecter|Disconnetti|接続を解除|연결 해제|Desconectar|Отключить|Bağlantıyı kes|断开连接|中斷連結
Save|Enregistrer|Salva|保存|저장|Salvar|Сохранить|Kaydet|保存|儲存
Video upscaling with Topaz AI|Augmentation de la résolution vidéo avec Topaz AI|Aumento della risoluzione video con Topaz AI|Topaz AI による動画のアップスケール|Topaz AI로 동영상 업스케일|Aumento de resolução de vídeo com Topaz AI|Увеличение разрешения видео с Topaz AI|Topaz AI ile video çözünürlüğü artırma|使用 Topaz AI 提升视频分辨率|使用 Topaz AI 提升影片解析度
Webhooks|Webhooks|Webhook|Webhook|웹훅|Webhooks|Вебхуки|Webhook'lar|Webhook|Webhook
Each finished export is sent, signed, to these addresses, for Make, Zapier or n8n to pass on to TikTok, Instagram and elsewhere|Chaque export terminé est envoyé, signé, à ces adresses, pour que Make, Zapier ou n8n le transmettent à TikTok, Instagram et ailleurs|Ogni esportazione completata viene inviata, firmata, a questi indirizzi, perché Make, Zapier o n8n la passino a TikTok, Instagram e altrove|書き出しが完了するたびに、署名付きでこれらのアドレスへ送信します。Make、Zapier、n8n から TikTok や Instagram などへ渡せます|내보내기가 끝날 때마다 서명과 함께 이 주소로 보내며, Make, Zapier, n8n이 TikTok, Instagram 등으로 전달할 수 있습니다|Cada exportação concluída é enviada, assinada, para estes endereços, para que Make, Zapier ou n8n a repassem ao TikTok, Instagram e outros|Каждый готовый экспорт отправляется с подписью на эти адреса, чтобы Make, Zapier или n8n передали его в TikTok, Instagram и другие сервисы|Biten her dışa aktarım imzalı olarak bu adreslere gönderilir; Make, Zapier veya n8n onu TikTok, Instagram ve başka yerlere aktarabilir|每次导出完成后，都会带签名发送到这些地址，供 Make、Zapier 或 n8n 转发到 TikTok、Instagram 等平台|每次匯出完成後，都會帶簽章傳送到這些位址，供 Make、Zapier 或 n8n 轉發到 TikTok、Instagram 等平台
https://… webhook address|https://… adresse du webhook|https://… indirizzo del webhook|https://… Webhook のアドレス|https://… 웹훅 주소|https://… endereço do webhook|https://… адрес вебхука|https://… webhook adresi|https://… Webhook 地址|https://… Webhook 位址
Send the video file too|Envoyer aussi le fichier vidéo|Invia anche il file video|動画ファイルも送信|동영상 파일도 보내기|Enviar também o arquivo de vídeo|Отправлять и видеофайл|Video dosyasını da gönder|同时发送视频文件|同時傳送影片檔案
Signing secret|Secret de signature|Segreto di firma|署名シークレット|서명 시크릿|Segredo de assinatura|Секрет подписи|İmza anahtarı|签名密钥|簽章密鑰
Copy|Copier|Copia|コピー|복사|Copiar|Копировать|Kopyala|复制|複製
Secret copied|Secret copié|Segreto copiato|シークレットをコピーしました|시크릿을 복사했습니다|Segredo copiado|Секрет скопирован|Anahtar kopyalandı|已复制密钥|已複製密鑰
Nothing sent yet|Rien d'envoyé pour l'instant|Ancora nulla inviato|まだ送信していません|아직 보낸 내용 없음|Nada enviado ainda|Пока ничего не отправлено|Henüz bir şey gönderilmedi|尚未发送|尚未傳送
Last delivery arrived|Dernier envoi reçu|Ultimo invio arrivato|前回の送信は届きました|마지막 전송 성공|Última entrega recebida|Последняя доставка прошла|Son gönderim ulaştı|上次发送已送达|上次傳送已送達
Last delivery failed|Dernier envoi échoué|Ultimo invio non riuscito|前回の送信は失敗しました|마지막 전송 실패|Última entrega falhou|Последняя доставка не удалась|Son gönderim başarısız|上次发送失败|上次傳送失敗
A webhook address starts with https:// or http://|Une adresse de webhook commence par https:// ou http://|Un indirizzo webhook inizia con https:// o http://|Webhook のアドレスは https:// または http:// で始まります|웹훅 주소는 https:// 또는 http://로 시작합니다|Um endereço de webhook começa com https:// ou http://|Адрес вебхука начинается с https:// или http://|Webhook adresi https:// veya http:// ile başlar|Webhook 地址以 https:// 或 http:// 开头|Webhook 位址以 https:// 或 http:// 開頭
Add a Topaz key in Settings to use Topaz|Ajoutez une clé Topaz dans les réglages pour utiliser Topaz|Aggiungi una chiave Topaz nelle impostazioni per usare Topaz|Topaz を使うには、設定で Topaz のキーを追加してください|Topaz를 사용하려면 설정에서 Topaz 키를 추가하세요|Adicione uma chave da Topaz nas configurações para usar o Topaz|Чтобы использовать Topaz, добавьте ключ Topaz в настройках|Topaz'ı kullanmak için Ayarlar'da bir Topaz anahtarı ekleyin|要使用 Topaz，请在设置中添加 Topaz 密钥|要使用 Topaz，請在設定中新增 Topaz 金鑰
Upscale…|Augmenter la résolution…|Aumenta risoluzione…|アップスケール…|업스케일…|Aumentar resolução…|Увеличить разрешение…|Çözünürlüğü artır…|提升分辨率…|提升解析度…
Upscale|Augmenter la résolution|Aumenta risoluzione|アップスケール|업스케일|Aumentar resolução|Увеличить разрешение|Çözünürlüğü artır|提升分辨率|提升解析度
Method|Méthode|Metodo|方式|방식|Método|Метод|Yöntem|方法|方法
Lanczos|Lanczos|Lanczos|Lanczos|Lanczos|Lanczos|Lanczos|Lanczos|Lanczos|Lanczos
Lanczos, sharpened|Lanczos, accentué|Lanczos, più nitido|Lanczos（シャープ）|Lanczos, 선명하게|Lanczos, com nitidez|Lanczos с резкостью|Lanczos, keskinleştirilmiş|Lanczos（锐化）|Lanczos（銳化）
AI (Real-ESRGAN, on this machine)|IA (Real-ESRGAN, sur cet appareil)|IA (Real-ESRGAN, su questo computer)|AI（Real-ESRGAN、このデバイスで実行）|AI (Real-ESRGAN, 이 기기에서 실행)|IA (Real-ESRGAN, neste computador)|ИИ (Real-ESRGAN, на этом устройстве)|Yapay zekâ (Real-ESRGAN, bu cihazda)|AI（Real-ESRGAN，在本机运行）|AI（Real-ESRGAN，在本機執行）
Runs Real-ESRGAN on this machine: sharper than resampling, free, and slower; video takes a while.|Exécute Real-ESRGAN sur cet appareil : plus net que le rééchantillonnage, gratuit et plus lent ; la vidéo prend du temps.|Esegue Real-ESRGAN su questo computer: più nitido del ricampionamento, gratuito e più lento; i video richiedono tempo.|このデバイスでReal-ESRGANを実行します。リサンプリングより鮮明で無料ですが、処理は遅く、動画には時間がかかります。|이 기기에서 Real-ESRGAN을 실행합니다. 리샘플링보다 선명하고 무료이지만 더 느리며, 동영상은 시간이 걸립니다.|Executa o Real-ESRGAN neste computador: mais nítido que a reamostragem, gratuito e mais lento; vídeos levam um tempo.|Запускает Real-ESRGAN на этом устройстве: чётче передискретизации, бесплатно и медленнее; видео обрабатывается долго.|Real-ESRGAN'ı bu cihazda çalıştırır: yeniden örneklemeden daha keskin, ücretsiz ve daha yavaş; video biraz zaman alır.|在本机运行 Real-ESRGAN：比重采样更清晰、免费，但更慢；视频需要一段时间。|在本機執行 Real-ESRGAN：比重新取樣更清晰、免費，但較慢；影片需要一段時間。
Download the AI model (64 MB)|Télécharger le modèle d’IA (64 Mo)|Scarica il modello IA (64 MB)|AIモデルをダウンロード（64 MB）|AI 모델 다운로드 (64MB)|Baixar o modelo de IA (64 MB)|Скачать модель ИИ (64 МБ)|Yapay zekâ modelini indir (64 MB)|下载 AI 模型（64 MB）|下載 AI 模型（64 MB）
Downloading the AI model…|Téléchargement du modèle d’IA…|Download del modello IA…|AIモデルをダウンロード中…|AI 모델 다운로드 중…|Baixando o modelo de IA…|Скачивание модели ИИ…|Yapay zekâ modeli indiriliyor…|正在下载 AI 模型…|正在下載 AI 模型…
Bicubic|Bicubique|Bicubico|バイキュービック|바이큐빅|Bicúbico|Бикубический|Bikübik|双三次|雙三次
Topaz AI|Topaz AI|Topaz AI|Topaz AI|Topaz AI|Topaz AI|Topaz AI|Topaz AI|Topaz AI|Topaz AI
Result: {size}|Résultat : {size}|Risultato: {size}|出力：{size}|결과: {size}|Resultado: {size}|Результат: {size}|Sonuç: {size}|结果：{size}|結果：{size}
Up to {limit} pixels on the long side here|Jusqu'à {limit} pixels sur le grand côté ici|Fino a {limit} pixel sul lato lungo qui|ここでは長辺 {limit} ピクセルまで|여기서는 긴 변 {limit}픽셀까지|Até {limit} pixels no lado maior aqui|Здесь до {limit} пикселей по длинной стороне|Burada uzun kenarda en fazla {limit} piksel|此处长边最多 {limit} 像素|此處長邊最多 {limit} 像素
Get estimate|Obtenir une estimation|Ottieni una stima|見積もりを取得|견적 받기|Obter estimativa|Получить оценку|Tahmin al|获取估算|取得估算
Estimate: {credits} credits, about {minutes} min|Estimation : {credits} crédits, environ {minutes} min|Stima: {credits} crediti, circa {minutes} min|見積もり：{credits} クレジット、約 {minutes} 分|견적: {credits} 크레딧, 약 {minutes}분|Estimativa: {credits} créditos, cerca de {minutes} min|Оценка: {credits} кредитов, около {minutes} мин|Tahmin: {credits} kredi, yaklaşık {minutes} dk|估算：{credits} 点数，约 {minutes} 分钟|估算：{credits} 點數，約 {minutes} 分鐘
Upscale for {credits} credits|Lancer pour {credits} crédits|Avvia per {credits} crediti|{credits} クレジットで実行|{credits} 크레딧으로 실행|Executar por {credits} créditos|Запустить за {credits} кредитов|{credits} krediyle başlat|花费 {credits} 点数开始|花費 {credits} 點數開始
Topaz works on video|Topaz traite la vidéo|Topaz lavora sui video|Topaz は動画専用です|Topaz는 동영상 전용입니다|Topaz funciona com vídeo|Topaz работает только с видео|Topaz yalnızca videoda çalışır|Topaz 仅适用于视频|Topaz 僅適用於影片
Upscaling|Augmentation de la résolution|Aumento della risoluzione|アップスケール中|업스케일 중|Aumentando a resolução|Увеличение разрешения|Çözünürlük artırılıyor|正在提升分辨率|正在提升解析度
Runs in Topaz Labs' cloud with your key; you see the credits before anything is charged.|S'exécute dans le cloud de Topaz Labs avec votre clé ; vous voyez les crédits avant tout débit.|Viene eseguito nel cloud di Topaz Labs con la tua chiave; vedi i crediti prima di qualsiasi addebito.|あなたのキーで Topaz Labs のクラウドで処理されます。課金前にクレジット数を確認できます。|내 키로 Topaz Labs 클라우드에서 실행됩니다. 청구 전에 크레딧을 확인할 수 있습니다.|Roda na nuvem da Topaz Labs com a sua chave; você vê os créditos antes de qualquer cobrança.|Выполняется в облаке Topaz Labs с вашим ключом; стоимость в кредитах видна до списания.|Anahtarınızla Topaz Labs bulutunda çalışır; ücretlendirmeden önce krediyi görürsünüz.|使用你的密钥在 Topaz Labs 云端运行；扣费前会先显示所需点数。|使用你的金鑰在 Topaz Labs 雲端執行；扣款前會先顯示所需點數。
Stickers|Autocollants|Adesivi|ステッカー|스티커|Figurinhas|Стикеры|Çıkartmalar|贴纸|貼紙
Music|Musique|Musica|音楽|음악|Música|Музыка|Müzik|音乐|音樂
Sounds|Sons|Suoni|効果音|효과음|Sons|Звуки|Sesler|音效|音效
Add to Media|Ajouter aux médias|Aggiungi ai media|メディアに追加|미디어에 추가|Adicionar à mídia|Добавить в медиа|Medyaya ekle|添加到媒体|新增至媒體
Added to Media|Ajouté aux médias|Aggiunto ai media|メディアに追加しました|미디어에 추가됨|Adicionado à mídia|Добавлено в медиа|Medyaya eklendi|已添加到媒体|已新增至媒體
Play|Écouter|Ascolta|再生|재생|Ouvir|Воспроизвести|Çal|播放|播放
Stop|Arrêter|Ferma|停止|정지|Parar|Остановить|Durdur|停止|停止
Preparing the library|Préparation de la bibliothèque|Preparazione della libreria|ライブラリを準備中|라이브러리 준비 중|Preparando a biblioteca|Подготовка библиотеки|Kütüphane hazırlanıyor|正在准备素材库|正在準備素材庫
Made by formcut: free to use in any video, no credit needed|Créé par formcut : libre d'utilisation dans toute vidéo, sans mention requise|Creato da formcut: libero da usare in qualsiasi video, senza citazione|formcut 製：どの動画でも無料で使え、クレジット表記は不要です|formcut 제작: 모든 동영상에서 무료로 사용 가능, 출처 표기 불필요|Feito pelo formcut: uso livre em qualquer vídeo, sem necessidade de crédito|Создано formcut: можно бесплатно использовать в любом видео без указания автора|formcut tarafından yapıldı: her videoda ücretsiz kullanılabilir, kaynak belirtmek gerekmez|由 formcut 制作：可在任何视频中免费使用，无需署名|由 formcut 製作：可在任何影片中免費使用，無需署名
Shapes|Formes|Forme|図形|도형|Formas|Фигуры|Şekiller|形状|形狀
Arrows|Flèches|Frecce|矢印|화살표|Setas|Стрелки|Oklar|箭头|箭頭
Callouts|Bulles et repères|Fumetti e richiami|吹き出し・強調|말풍선·강조|Balões e destaques|Выноски|Belirtme öğeleri|标注|標註
Labels|Étiquettes|Etichette|ラベル|라벨|Rótulos|Метки|Etiketler|标签|標籤
Faces|Visages|Facce|顔|표정|Rostos|Лица|Yüzler|表情|表情
Icons|Icônes|Icone|アイコン|아이콘|Ícones|Значки|Simgeler|图标|圖示
Whooshes|Sons de transition|Suoni di transizione|トランジション音|전환 효과음|Sons de transição|Звуки переходов|Geçiş sesleri|转场音效|轉場音效
Interface|Interface|Interfaccia|UI効果音|인터페이스|Interface|Интерфейс|Arayüz|界面|介面
Impacts|Impacts|Impatti|インパクト|임팩트|Impactos|Удары|Darbeler|冲击|衝擊
Everyday|Quotidien|Quotidiano|日常音|생활 소리|Cotidiano|Бытовые|Günlük|日常|日常
Calm|Calme|Calmo|穏やか|차분함|Calmo|Спокойное|Sakin|舒缓|舒緩
Upbeat|Entraînant|Vivace|アップビート|경쾌함|Animado|Бодрое|Hareketli|欢快|歡快
Dramatic|Dramatique|Drammatico|ドラマチック|극적임|Dramático|Драматичное|Dramatik|戏剧性|戲劇性
Retro|Rétro|Retrò|レトロ|레트로|Retrô|Ретро|Retro|复古|復古
Whoosh|Whoosh|Whoosh|ヒュッ|휙|Whoosh|Свист|Whoosh|嗖|嗖
Swoosh|Swoosh|Swoosh|シュッ|쉭|Swoosh|Взмах|Swoosh|唰|唰
Riser|Montée|Crescendo|ライザー|라이저|Subida|Нарастание|Yükselen|上升音效|上升音效
Downlifter|Descente|Discesa|ダウンリフター|다운리프터|Descida|Спад|Alçalan|下降音效|下降音效
Pop|Pop|Pop|ポン|뽁|Pop|Хлопок|Pıt|啵|啵
Click|Clic|Clic|クリック|클릭|Clique|Щелчок|Tık|点击|點擊
Tick|Tic|Tic|カチッ|틱|Tique|Тик|Tik|嘀嗒|嘀嗒
Ding|Ding|Din|チーン|딩|Ding|Дзинь|Ding|叮|叮
Chime|Carillon|Rintocco|チャイム|차임|Sininho|Перезвон|Çan sesi|铃声|鈴聲
Success|Réussite|Successo|成功|성공|Sucesso|Успех|Başarı|成功|成功
Error|Erreur|Errore|エラー|오류|Erro|Ошибка|Hata|错误|錯誤
Coin|Pièce|Moneta|コイン|코인|Moeda|Монета|Jeton|金币|金幣
Boom|Boum|Bum|ドーン|쾅|Bum|Бум|Bum|轰|轟
Heartbeat|Battement de cœur|Battito|心臓の鼓動|심장 박동|Batimento|Сердцебиение|Kalp atışı|心跳|心跳
Glitch|Glitch|Glitch|グリッチ|글리치|Glitch|Глитч|Glitch|故障音|故障音
Camera shutter|Obturateur|Otturatore|シャッター音|카메라 셔터|Obturador|Затвор камеры|Deklanşör|快门声|快門聲
Typewriter|Machine à écrire|Macchina da scrivere|タイプライター|타자기|Máquina de escrever|Пишущая машинка|Daktilo|打字机|打字機
SAM 2.1 video tracking|Suivi vidéo SAM 2.1|Tracciamento video SAM 2.1|SAM 2.1 動画トラッキング|SAM 2.1 동영상 추적|Rastreamento de vídeo SAM 2.1|Видеотрекинг SAM 2.1|SAM 2.1 video izleme|SAM 2.1 视频跟踪|SAM 2.1 影片追蹤
Import SAM 2.1 video tracking|Importer le suivi vidéo SAM 2.1|Importa il tracciamento video SAM 2.1|SAM 2.1 動画トラッキングを読み込む|SAM 2.1 동영상 추적 가져오기|Importar rastreamento de vídeo SAM 2.1|Импортировать видеотрекинг SAM 2.1|SAM 2.1 video izlemeyi içe aktar|导入 SAM 2.1 视频跟踪|匯入 SAM 2.1 影片追蹤
Draw a box around it|Tracer un cadre autour|Disegna un riquadro attorno|枠で囲む|상자로 감싸기|Desenhar uma caixa em volta|Обвести рамкой|Etrafına kutu çiz|框选|框選
Drag a box around what to keep|Tracez un cadre autour de ce qu'il faut garder|Trascina un riquadro attorno a ciò da tenere|残したいものを枠で囲んでください|남길 대상을 상자로 감싸세요|Arraste uma caixa em volta do que manter|Обведите рамкой то, что нужно оставить|Tutulacak şeyin etrafına bir kutu çizin|拖出一个框，框住要保留的内容|拖出一個框，框住要保留的內容
Kept what is in the box|Gardé ce qui est dans le cadre|Tenuto ciò che è nel riquadro|枠内のものを残しました|상자 안의 대상을 남겼습니다|Mantido o que está na caixa|Оставлено то, что в рамке|Kutunun içindeki tutuldu|已保留框内的内容|已保留框內的內容
A person|Une personne|Una persona|人物|사람|Uma pessoa|Человек|Bir kişi|人物|人物
Anything (object)|N'importe quoi (objet)|Qualsiasi cosa (oggetto)|何でも (物体)|무엇이든 (물체)|Qualquer coisa (objeto)|Что угодно (объект)|Herhangi bir şey (nesne)|任意事物 (物体)|任意事物 (物體)
Subject (Auto)|Sujet (auto)|Soggetto (auto)|被写体 (自動)|피사체 (자동)|Assunto (automático)|Объект съёмки (авто)|Konu (otomatik)|主体 (自动)|主體 (自動)
Smart restore|Restauration intelligente|Ripristino intelligente|スマート復元|스마트 복원|Restauração inteligente|Умное восстановление|Akıllı geri getirme|智能恢复|智慧復原
Smart erase|Effacement intelligent|Cancellazione intelligente|スマート消去|스마트 지우기|Apagar inteligente|Умное стирание|Akıllı silme|智能擦除|智慧擦除
Fine edges (IS-Net)|Contours fins (IS-Net)|Bordi precisi (IS-Net)|精細なエッジ (IS-Net)|정밀한 가장자리 (IS-Net)|Bordas finas (IS-Net)|Точные края (IS-Net)|İnce kenarlar (IS-Net)|精细边缘 (IS-Net)|精細邊緣 (IS-Net)
Video matting (people)|Détourage vidéo (personnes)|Scontorno video (persone)|動画マッティング (人物)|동영상 매팅 (인물)|Recorte de vídeo (pessoas)|Видеоматтинг (люди)|Video maskeleme (kişiler)|视频抠像 (人物)|影片摳像 (人物)
Point to select (SAM 2)|Pointer pour sélectionner (SAM 2)|Punta per selezionare (SAM 2)|ポイントして選択 (SAM 2)|가리켜서 선택 (SAM 2)|Apontar para selecionar (SAM 2)|Выбор указанием (SAM 2)|İşaretleyerek seç (SAM 2)|点选对象 (SAM 2)|點選物件 (SAM 2)
Media|Médias|Media|メディア|미디어|Mídia|Медиа|Medya|媒体|媒體
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
Subtitle files: bring captions in from an SRT or VTT file, or take this track's captions out as one|Fichiers de sous-titres : importez des sous-titres depuis un fichier SRT ou VTT, ou exportez ceux de cette piste sous cette forme|File di sottotitoli: importa i sottotitoli da un file SRT o VTT, o esporta quelli di questa traccia in quel formato|字幕ファイル: SRT または VTT ファイルから字幕を読み込む、またはこのトラックの字幕をファイルに書き出す|자막 파일: SRT 또는 VTT 파일에서 자막을 가져오거나 이 트랙의 자막을 파일로 내보냅니다|Arquivos de legenda: traga legendas de um arquivo SRT ou VTT, ou exporte as desta faixa como um|Файлы субтитров: импортируйте субтитры из файла SRT или VTT или экспортируйте субтитры этой дорожки в такой файл|Altyazı dosyaları: SRT veya VTT dosyasından altyazı alın ya da bu parçanın altyazılarını dosya olarak verin|字幕文件：从 SRT 或 VTT 文件导入字幕，或将此轨道的字幕导出为文件|字幕檔案：從 SRT 或 VTT 檔案匯入字幕，或將此軌道的字幕匯出為檔案
Import subtitles|Importer des sous-titres|Importa sottotitoli|字幕を読み込む|자막 가져오기|Importar legendas|Импортировать субтитры|Altyazı içe aktar|导入字幕|匯入字幕
Export SRT|Exporter en SRT|Esporta SRT|SRT を書き出す|SRT 내보내기|Exportar SRT|Экспортировать SRT|SRT olarak dışa aktar|导出 SRT|匯出 SRT
Export VTT|Exporter en VTT|Esporta VTT|VTT を書き出す|VTT 내보내기|Exportar VTT|Экспортировать VTT|VTT olarak dışa aktar|导出 VTT|匯出 VTT
No captions found in that file: it should be SRT or WebVTT|Aucun sous-titre trouvé dans ce fichier : il doit être au format SRT ou WebVTT|Nessun sottotitolo trovato in quel file: dovrebbe essere SRT o WebVTT|そのファイルに字幕が見つかりません。SRT か WebVTT が必要です|해당 파일에서 자막을 찾을 수 없습니다. SRT 또는 WebVTT여야 합니다|Nenhuma legenda encontrada nesse arquivo: ele deve ser SRT ou WebVTT|В этом файле не найдено субтитров: он должен быть в формате SRT или WebVTT|Bu dosyada altyazı bulunamadı: SRT veya WebVTT olmalı|该文件中未找到字幕：应为 SRT 或 WebVTT|該檔案中找不到字幕：應為 SRT 或 WebVTT
No captions on that track|Aucun sous-titre sur cette piste|Nessun sottotitolo su quella traccia|そのトラックに字幕はありません|해당 트랙에 자막이 없습니다|Nenhuma legenda nessa faixa|На этой дорожке нет субтитров|Bu parçada altyazı yok|该轨道上没有字幕|該軌道上沒有字幕
Exported|Exporté|Esportato|書き出しました|내보냈습니다|Exportado|Экспортировано|Dışa aktarıldı|已导出|已匯出
Add adjustment layer|Ajouter un calque de réglage|Aggiungi livello di regolazione|調整レイヤーを追加|조정 레이어 추가|Adicionar camada de ajuste|Добавить корректирующий слой|Ayarlama katmanı ekle|添加调整图层|新增調整圖層
A clip with no footage of its own: its effects and colour apply to everything beneath it for as long as it lasts|Un clip sans image propre : ses effets et sa couleur s'appliquent à tout ce qui se trouve dessous pendant sa durée|Una clip senza immagini proprie: i suoi effetti e il colore si applicano a tutto ciò che sta sotto per la sua durata|映像を持たないクリップ。持続する間、下にあるすべてにエフェクトと色が適用されます|자체 영상이 없는 클립: 지속되는 동안 아래의 모든 것에 효과와 색상이 적용됩니다|Um clipe sem imagem própria: seus efeitos e cor se aplicam a tudo abaixo dele enquanto durar|Клип без собственного материала: его эффекты и цвет применяются ко всему под ним, пока он длится|Kendi görüntüsü olmayan bir klip: efektleri ve rengi, sürdüğü süre boyunca altındaki her şeye uygulanır|没有自身素材的片段：在其持续期间，它的效果和色彩会应用于其下方的所有内容|沒有自身素材的片段：在其持續期間，它的效果和色彩會套用到其下方的所有內容
Adjustment|Réglage|Regolazione|調整|조정|Ajuste|Коррекция|Ayarlama|调整|調整
Caption style|Style des sous-titres|Stile dei sottotitoli|字幕スタイル|자막 스타일|Estilo da legenda|Стиль субтитров|Altyazı stili|字幕样式|字幕樣式
Plain|Simple|Semplice|標準|기본|Simples|Обычный|Sade|普通|一般
Highlight the word|Mettre le mot en couleur|Evidenzia la parola|単語を色で強調|단어 강조|Destacar a palavra|Выделять слово цветом|Kelimeyi vurgula|高亮单词|標示單字
Pop the word|Agrandir le mot|Ingrandisci la parola|単語を大きく|단어 키우기|Ampliar a palavra|Увеличивать слово|Kelimeyi büyüt|放大单词|放大單字
Box the word|Encadrer le mot|Riquadra la parola|単語を枠で囲む|단어 상자 표시|Emoldurar a palavra|Слово в рамке|Kelimeyi kutula|单词加框|單字加框
Key by|Incruster selon|Keying per|キーの方式|키 방식|Recortar por|Ключ по|Anahtar ölçütü|抠像依据|去背依據
Hue distance|Distance de teinte|Distanza di tinta|色相の距離|색조 거리|Distância de matiz|Расстояние оттенка|Ton uzaklığı|色相距离|色相距離
Colour difference (screens)|Différence de couleur (écrans)|Differenza di colore (schermi)|色差（画面）|색상 차이(화면)|Diferença de cor (telas)|Разность цветов (экраны)|Renk farkı (ekranlar)|色差（屏幕）|色差（螢幕）
Brightest channel (screens)|Canal le plus lumineux (écrans)|Canale più luminoso (schermi)|最も明るいチャンネル（画面）|가장 밝은 채널(화면)|Canal mais brilhante (telas)|Самый яркий канал (экраны)|En parlak kanal (ekranlar)|最亮通道（屏幕）|最亮通道（螢幕）
Track by|Suivre par|Traccia tramite|トラッキング方法|트래킹 기준|Rastrear por|Отслеживать по|İzleme ölçütü|跟踪依据|追蹤依據
Its picture (planar)|Son image (planaire)|La sua immagine (planare)|画像（プレーナー）|이미지(평면)|Sua imagem (planar)|По изображению (планарно)|Görüntüsü (düzlemsel)|画面内容（平面）|畫面內容（平面）
A green screen's edges|Bords d'un écran vert|Bordi di uno schermo verde|グリーンスクリーンの縁|그린 스크린 가장자리|Bordas de uma tela verde|Края зелёного экрана|Yeşil perdenin kenarları|绿幕边缘|綠幕邊緣
A blue screen's edges|Bords d'un écran bleu|Bordi di uno schermo blu|ブルースクリーンの縁|블루 스크린 가장자리|Bordas de uma tela azul|Края синего экрана|Mavi perdenin kenarları|蓝幕边缘|藍幕邊緣
Spill|Débordement|Fuoriuscita|スピル|스필|Vazamento|Засветка|Taşma|溢色|溢色
Key hold-out for this clip|Protection de l'incrustation pour ce clip|Protezione del keying per questa clip|このクリップのキー保護|이 클립의 키 보호|Proteção do chroma para este clipe|Защита ключа для этого клипа|Bu klip için anahtar koruması|此片段的抠像保护|此片段的去背保護
Turn on this clip's chroma key first|Activez d'abord l'incrustation de ce clip|Attiva prima il chroma key di questa clip|まずこのクリップのクロマキーをオンにしてください|먼저 이 클립의 크로마 키를 켜세요|Ative primeiro o chroma key deste clipe|Сначала включите хромакей этого клипа|Önce bu klibin renk anahtarını açın|请先开启此片段的色度抠像|請先開啟此片段的色度去背
Hold-out applied to this clip's key|Protection appliquée à l'incrustation de ce clip|Protezione applicata al keying di questa clip|このクリップのキーに保護を適用しました|이 클립의 키에 보호를 적용했습니다|Proteção aplicada ao chroma deste clipe|Защита применена к ключу клипа|Koruma bu klibin anahtarına uygulandı|已将保护应用到此片段的抠像|已將保護套用到此片段的去背
Remove key hold-out|Retirer la protection de l'incrustation|Rimuovi protezione del keying|キー保護を外す|키 보호 제거|Remover proteção do chroma|Убрать защиту ключа|Anahtar korumasını kaldır|移除抠像保护|移除去背保護
Click an object to outline it (SAM 2.1)|Cliquez sur un objet pour le détourer (SAM 2.1)|Fai clic su un oggetto per contornarlo (SAM 2.1)|オブジェクトをクリックして輪郭を作成 (SAM 2.1)|개체를 클릭해 윤곽을 만듭니다 (SAM 2.1)|Clique em um objeto para contorná-lo (SAM 2.1)|Щёлкните объект, чтобы обвести его (SAM 2.1)|Bir nesneye tıklayıp çevresini çizin (SAM 2.1)|点击对象以勾勒轮廓（SAM 2.1）|點按物件以勾勒輪廓（SAM 2.1）
Outlining…|Détourage…|Contornando…|輪郭を作成中…|윤곽 만드는 중…|Contornando…|Обводка…|Çevre çiziliyor…|正在勾勒…|正在勾勒…
Add key|Ajouter une clé|Aggiungi chiave|キーを追加|키 추가|Adicionar chave|Добавить ключ|Anahtar ekle|添加关键帧|新增關鍵影格
Delete key|Supprimer la clé|Elimina chiave|キーを削除|키 삭제|Excluir chave|Удалить ключ|Anahtarı sil|删除关键帧|刪除關鍵影格
Double-click a shape's edge to add a point|Double-cliquez sur un bord pour ajouter un point|Doppio clic su un bordo per aggiungere un punto|シェイプの辺をダブルクリックでポイント追加|셰이프 가장자리를 더블클릭해 포인트 추가|Clique duplo na borda para adicionar um ponto|Двойной щелчок по краю добавляет точку|Nokta eklemek için kenara çift tıklayın|双击形状边缘添加点|雙擊形狀邊緣以新增點
Smooth (X-Spline)|Lisse (X-Spline)|Morbido (X-Spline)|スムーズ (X-Spline)|부드럽게 (X-Spline)|Suave (X-Spline)|Гладкая (X-Spline)|Yumuşak (X-Spline)|平滑（X-Spline）|平滑（X-Spline）
Überkey|Überkey|Überkey|Überkey|Überkey|Überkey|Überkey|Überkey|Überkey|Überkey
Tension|Tension|Tensione|テンション|장력|Tensão|Натяжение|Gerginlik|张力|張力
Edge feather|Contour progressif|Sfumatura bordo|エッジのぼかし|가장자리 흐림|Suavizar borda|Растушёвка края|Kenar yumuşatma|边缘羽化|邊緣羽化
Link to track|Lier au suivi|Collega al tracciamento|トラッキングにリンク|트래킹에 연결|Vincular ao rastreamento|Связать с трекингом|İzlemeye bağla|链接到跟踪|連結到追蹤
Its own track|Son propre suivi|Il proprio tracciamento|自身のトラッキング|자체 트래킹|Seu próprio rastreamento|Свой трекинг|Kendi izi|自身的跟踪|自身的追蹤
This layer is not tracked: moving its points keys its shape on this frame|Ce calque n'est pas suivi : déplacer ses points crée une clé sur cette image|Questo livello non è tracciato: spostare i punti crea una chiave in questo fotogramma|このレイヤーはトラッキングされません。ポイントを動かすとこのフレームにキーが付きます|이 레이어는 트래킹되지 않습니다. 포인트를 움직이면 이 프레임에 키가 생깁니다|Esta camada não é rastreada: mover os pontos cria uma chave neste quadro|Этот слой не отслеживается: сдвиг точек ставит ключ на этом кадре|Bu katman izlenmiyor: noktaları taşımak bu karede anahtar ekler|此图层未跟踪：移动点会在此帧添加关键帧|此圖層未追蹤：移動點會在此影格加入關鍵影格
AdjustTrack|AdjustTrack|AdjustTrack|AdjustTrack|AdjustTrack|AdjustTrack|AdjustTrack|AdjustTrack|AdjustTrack|AdjustTrack
Where the track drifts, move a point back onto its feature|Là où le suivi dérive, ramenez un point sur son repère|Dove il tracciamento deriva, riporta un punto sul suo dettaglio|トラッキングがずれたら、ポイントを元の特徴点に戻します|트래킹이 어긋나면 포인트를 원래 지점으로 되돌리세요|Onde o rastreamento desvia, devolva um ponto ao seu detalhe|Где трекинг уплывает, верните точку на её деталь|İzleme kaydığında noktayı kendi ayrıntısına geri taşıyın|跟踪漂移时，把点移回它的特征处|追蹤漂移時，把點移回它的特徵處
New point|Nouveau point|Nuovo punto|新規ポイント|새 포인트|Novo ponto|Новая точка|Yeni nokta|新建点|新增點
Next point|Point suivant|Punto successivo|次のポイント|다음 포인트|Próximo ponto|Следующая точка|Sonraki nokta|下一个点|下一個點
Set master|Définir le maître|Imposta master|マスターに設定|마스터로 설정|Definir mestre|Сделать главной|Ana olarak ayarla|设为主帧|設為主影格
Delete point|Supprimer le point|Elimina punto|ポイントを削除|포인트 삭제|Excluir ponto|Удалить точку|Noktayı sil|删除点|刪除點
Nudge|Décaler|Sposta|微調整|미세 이동|Deslocar|Сдвинуть|Kaydır|微调|微調
Search region|Zone de recherche|Regione di ricerca|検索領域|검색 영역|Região de busca|Область поиска|Arama bölgesi|搜索区域|搜尋區域
Maximum motion|Mouvement maximal|Movimento massimo|最大移動量|최대 움직임|Movimento máximo|Макс. движение|En fazla hareket|最大运动|最大運動
Auto nudge|Décalage auto|Spostamento automatico|自動微調整|자동 미세 이동|Deslocamento automático|Автосдвиг|Otomatik kaydır|自动微调|自動微調
Click where the new point goes|Cliquez où placer le nouveau point|Fai clic dove va il nuovo punto|新しいポイントの位置をクリック|새 포인트를 둘 곳을 클릭하세요|Clique onde fica o novo ponto|Щёлкните, куда поставить точку|Yeni noktanın yerine tıklayın|点击新点要放的位置|點按新點要放的位置
Matte for this clip|Cache pour ce clip|Maschera per questa clip|このクリップのマット|이 클립의 매트|Matte para este clipe|Маска для этого клипа|Bu klip için matte|此片段的遮罩|此片段的遮罩
Matte applied to this clip|Cache appliqué à ce clip|Maschera applicata a questa clip|このクリップにマットを適用しました|이 클립에 매트를 적용했습니다|Matte aplicado a este clipe|Маска применена к этому клипу|Matte bu klibe uygulandı|已将遮罩应用到此片段|已將遮罩套用到此片段
Remove tracked matte|Retirer le cache suivi|Rimuovi maschera tracciata|トラッキングマットを外す|트래킹 매트 제거|Remover matte rastreado|Убрать отслеженную маску|İzlenen matte'ı kaldır|移除跟踪遮罩|移除追蹤遮罩
Apply to a clip|Appliquer à un clip|Applica a una clip|クリップに適用|클립에 적용|Aplicar a um clipe|Применить к клипу|Bir klibe uygula|应用到片段|套用到片段
Clip|Clip|Clip|クリップ|클립|Clipe|Клип|Klip|片段|片段
As|En tant que|Come|方式|방식|Como|Как|Biçim|方式|方式
Corner pin|Épinglage des coins|Pin degli angoli|コーナーピン|코너 핀|Pin de cantos|Угловая привязка|Köşe sabitleme|四角定位|四角定位
Position, scale and rotation|Position, échelle et rotation|Posizione, scala e rotazione|位置、スケール、回転|위치, 크기, 회전|Posição, escala e rotação|Положение, масштаб и поворот|Konum, ölçek ve döndürme|位置、缩放和旋转|位置、縮放和旋轉
Apply|Appliquer|Applica|適用|적용|Aplicar|Применить|Uygula|应用|套用
Applied to {clip}: {n} frames|Appliqué à {clip} : {n} images|Applicato a {clip}: {n} fotogrammi|{clip} に適用: {n} フレーム|{clip}에 적용: {n} 프레임|Aplicado a {clip}: {n} quadros|Применено к {clip}: {n} кадров|{clip} klibine uygulandı: {n} kare|已应用到 {clip}：{n} 帧|已套用到 {clip}：{n} 個影格
Place the layer's surface first|Placez d'abord la surface du calque|Posiziona prima la superficie del livello|まずレイヤーのサーフェスを配置してください|먼저 레이어의 서피스를 배치하세요|Posicione primeiro a superfície da camada|Сначала разместите поверхность слоя|Önce katmanın yüzeyini yerleştirin|请先放置图层的平面|請先放置圖層的平面
No other clip to apply to|Aucun autre clip auquel appliquer|Nessun'altra clip a cui applicare|適用できる他のクリップがありません|적용할 다른 클립이 없습니다|Nenhum outro clipe para aplicar|Нет другого клипа для применения|Uygulanacak başka klip yok|没有其他可应用的片段|沒有其他可套用的片段
Remove corner pin|Retirer l'épinglage des coins|Rimuovi pin degli angoli|コーナーピンを外す|코너 핀 제거|Remover pin de cantos|Убрать угловую привязку|Köşe sabitlemeyi kaldır|移除四角定位|移除四角定位
Motion blur (corner pin)|Flou de mouvement (épinglage des coins)|Sfocatura di movimento (pin degli angoli)|モーションブラー（コーナーピン）|모션 블러(코너 핀)|Desfoque de movimento (pin de cantos)|Размытие движения (угловая привязка)|Hareket bulanıklığı (köşe sabitleme)|运动模糊（四角定位）|動態模糊（四角定位）
Match light|Ajuster la lumière|Abbina la luce|ライトを合わせる|조명 맞추기|Igualar a luz|Подогнать свет|Işığı eşleştir|匹配光照|匹配光照
Match grain|Ajuster le grain|Abbina la grana|グレインを合わせる|그레인 맞추기|Igualar o grão|Подогнать зерно|Greni eşleştir|匹配颗粒|匹配顆粒
Match softness|Ajuster la douceur|Abbina la morbidezza|柔らかさを合わせる|부드러움 맞추기|Igualar a suavidade|Подогнать мягкость|Yumuşaklığı eşleştir|匹配柔和度|匹配柔和度
Motion blur (tracked matte)|Flou de mouvement (cache suivi)|Sfocatura di movimento (maschera tracciata)|モーションブラー（トラッキングマット）|모션 블러(트래킹 매트)|Desfoque de movimento (máscara rastreada)|Размытие движения (отслеживаемая маска)|Hareket bulanıklığı (izlenen maske)|运动模糊（跟踪遮罩）|動態模糊（追蹤遮罩）
Stopped at frame|Arrêté à l'image|Fermato al fotogramma|停止したフレーム:|멈춘 프레임:|Parado no quadro|Остановлено на кадре|Şu karede durdu:|停止于帧|停止於影格
Lost the plane at frame|Plan perdu à l'image|Piano perso al fotogramma|平面を見失ったフレーム:|평면을 놓친 프레임:|Plano perdido no quadro|Плоскость потеряна на кадре|Düzlem şu karede kayboldu:|平面丢失于帧|平面遺失於影格
Layers|Calques|Livelli|レイヤー|레이어|Camadas|Слои|Katmanlar|图层|圖層
New layer|Nouveau calque|Nuovo livello|新規レイヤー|새 레이어|Nova camada|Новый слой|Yeni katman|新建图层|新增圖層
Select and move points|Sélectionner et déplacer des points|Seleziona e sposta i punti|ポイントを選択して移動|포인트 선택 및 이동|Selecionar e mover pontos|Выбрать и двигать точки|Noktaları seç ve taşı|选择并移动点|選取並移動點
Draw a shape (double-click or Enter closes it)|Dessiner une forme (double-clic ou Entrée la ferme)|Disegna una forma (doppio clic o Invio la chiude)|シェイプを描く（ダブルクリックまたは Enter で閉じる）|셰이프 그리기(더블클릭 또는 Enter로 닫기)|Desenhar uma forma (clique duplo ou Enter a fecha)|Нарисовать фигуру (двойной щелчок или Enter замыкает)|Şekil çiz (çift tıklama veya Enter kapatır)|绘制形状（双击或回车闭合）|繪製形狀（雙擊或 Enter 閉合）
Draw a rectangle|Dessiner un rectangle|Disegna un rettangolo|長方形を描く|사각형 그리기|Desenhar um retângulo|Нарисовать прямоугольник|Dikdörtgen çiz|绘制矩形|繪製矩形
Delete shape|Supprimer la forme|Elimina forma|シェイプを削除|셰이프 삭제|Excluir forma|Удалить фигуру|Şekli sil|删除形状|刪除形狀
Surface|Surface|Superficie|サーフェス|서피스|Superfície|Поверхность|Yüzey|平面|平面
Grid|Grille|Griglia|グリッド|그리드|Grade|Сетка|Izgara|网格|網格
Trace|Trace|Traccia|軌跡|궤적|Rastro|След|İz|轨迹|軌跡
Stabilised|Stabilisé|Stabilizzato|スタビライズ|안정화|Estabilizado|Стабилизировано|Sabitlenmiş|稳定视图|穩定檢視
Align surface|Aligner la surface|Allinea superficie|サーフェスを合わせる|서피스 맞추기|Alinhar superfície|Выровнять поверхность|Yüzeyi hizala|对齐平面|對齊平面
Track backwards|Suivre en arrière|Traccia all'indietro|逆方向にトラッキング|뒤로 트래킹|Rastrear para trás|Трекинг назад|Geriye izle|向后跟踪|向後追蹤
Track one frame back|Suivre une image en arrière|Traccia un fotogramma indietro|1フレーム戻ってトラッキング|한 프레임 뒤로 트래킹|Rastrear um quadro para trás|Трекинг на кадр назад|Bir kare geri izle|向后跟踪一帧|向後追蹤一格
Track one frame forward|Suivre une image en avant|Traccia un fotogramma avanti|1フレーム進んでトラッキング|한 프레임 앞으로 트래킹|Rastrear um quadro para frente|Трекинг на кадр вперёд|Bir kare ileri izle|向前跟踪一帧|向前追蹤一格
Track forwards|Suivre en avant|Traccia in avanti|順方向にトラッキング|앞으로 트래킹|Rastrear para frente|Трекинг вперёд|İleri izle|向前跟踪|向前追蹤
Layer name|Nom du calque|Nome del livello|レイヤー名|레이어 이름|Nome da camada|Имя слоя|Katman adı|图层名称|圖層名稱
Visible|Visible|Visibile|表示|표시|Visível|Видимый|Görünür|可见|可見
Track this layer|Suivre ce calque|Traccia questo livello|このレイヤーをトラッキング|이 레이어 트래킹|Rastrear esta camada|Трекинг этого слоя|Bu katmanı izle|跟踪此图层|追蹤此圖層
Locked|Verrouillé|Bloccato|ロック|잠김|Bloqueada|Заблокирован|Kilitli|已锁定|已鎖定
Point on/off|Point actif/inactif|Punto attivo/inattivo|ポイントのオン/オフ|포인트 켜기/끄기|Ponto ativo/inativo|Точка вкл./выкл.|Nokta açık/kapalı|点开/关|點開/關
Make Bézier|Convertir en Bézier|Converti in Bézier|ベジェに変換|베지어로 변환|Converter em Bézier|Преобразовать в Безье|Bézier'e dönüştür|转换为贝塞尔|轉換為貝茲
In here|Début ici|Inizio qui|ここから開始|여기서 시작|Início aqui|Начало здесь|Başlangıç burada|从此处开始|從此處開始
Out here|Fin ici|Fine qui|ここで終了|여기서 끝|Fim aqui|Конец здесь|Bitiş burada|在此处结束|在此處結束
Group|Groupe|Gruppo|グループ|그룹|Grupo|Группа|Grup|组|群組
Create mask|Créer un masque|Crea maschera|マスクを作成|마스크 만들기|Criar máscara|Создать маску|Maske oluştur|创建蒙版|建立遮罩
Matte clip|Clip de cache|Clip maschera|マットクリップ|매트 클립|Clipe de máscara|Клип маски|Maske klibi|遮罩剪辑|遮罩片段
Dope sheet|Feuille d'exposition|Dope sheet|ドープシート|도프 시트|Folha de animação|Таблица ключей|Anahtar kare tablosu|摄影表|攝影表
Find faces|Trouver les visages|Trova volti|顔を検出|얼굴 찾기|Encontrar rostos|Найти лица|Yüzleri bul|查找人脸|尋找人臉
Matte Assist|Assistant de cache|Assistente maschera|マットアシスト|매트 어시스트|Assistente de máscara|Помощник маски|Maske yardımcısı|遮罩辅助|遮罩輔助
Freehand|Main levée|A mano libera|フリーハンド|자유형|À mão livre|От руки|Serbest çizim|手绘|手繪
Area brush|Pinceau de zone|Pennello area|エリアブラシ|영역 브러시|Pincel de área|Кисть области|Alan fırçası|区域画笔|區域筆刷
Magnetic: freehand clings to edges|Magnétique : le tracé suit les bords|Magnetico: il tratto si aggancia ai bordi|マグネット：フリーハンドが輪郭に吸着|자석: 자유형 선이 가장자리에 붙음|Magnético: o traço adere às bordas|Магнит: линия от руки прилипает к краям|Mıknatıs: serbest çizim kenarlara yapışır|磁性：手绘线吸附到边缘|磁性：手繪線吸附到邊緣
Snap to edges|Aligner sur les bords|Aggancia ai bordi|輪郭にスナップ|가장자리에 맞추기|Ajustar às bordas|Привязать к краям|Kenarlara yasla|吸附到边缘|吸附到邊緣
Stabilize this clip by the track|Stabiliser ce clip par le suivi|Stabilizza questa clip con il tracciamento|トラッキングでこのクリップを安定化|트래킹으로 이 클립 안정화|Estabilizar este clipe pelo rastreamento|Стабилизировать клип по трекингу|Bu klibi izlemeyle sabitle|按跟踪稳定此剪辑|依追蹤穩定此片段
ReOrient this clip to face the surface|Réorienter ce clip face à la surface|Riorienta questa clip verso la superficie|面に正対するようクリップを再配置|표면을 정면으로 보도록 클립 재배치|Reorientar este clipe de frente para a superfície|Развернуть клип к поверхности|Bu klibi yüzeye dönük yeniden yönlendir|将此剪辑重新定向为正对表面|將此片段重新定向為正對表面
Remove the object (render a clean clip)|Supprimer l'objet (rendre un clip propre)|Rimuovi l'oggetto (renderizza una clip pulita)|オブジェクトを除去（クリーンなクリップをレンダー）|오브젝트 제거(깨끗한 클립 렌더)|Remover o objeto (renderizar um clipe limpo)|Удалить объект (отрендерить чистый клип)|Nesneyi kaldır (temiz klip oluştur)|移除对象（渲染干净剪辑）|移除物件（算繪乾淨片段）
Remove takes the selected layer away: track another layer on the background first|La suppression retire le calque sélectionné : suivez d'abord un autre calque sur le fond|La rimozione toglie il livello selezionato: traccia prima un altro livello sullo sfondo|除去は選択したレイヤーを消します：先に背景の別レイヤーをトラッキングしてください|제거는 선택한 레이어를 지웁니다: 먼저 배경의 다른 레이어를 트래킹하세요|Remover tira a camada selecionada: rastreie primeiro outra camada no fundo|Удаление убирает выбранный слой: сначала отследите другой слой на фоне|Kaldırma seçili katmanı siler: önce arka planda başka bir katmanı izleyin|移除会去掉所选图层：请先跟踪背景上的另一个图层|移除會去掉所選圖層：請先追蹤背景上的另一個圖層
Removing the object, frame by frame…|Suppression de l'objet, image par image…|Rimozione dell'oggetto, fotogramma per fotogramma…|フレームごとにオブジェクトを除去中…|프레임별로 오브젝트 제거 중…|Removendo o objeto, quadro a quadro…|Удаление объекта, кадр за кадром…|Nesne kare kare kaldırılıyor…|正在逐帧移除对象…|正在逐格移除物件…
The clean clip is rendered: it is in the media bin|Le clip propre est rendu : il est dans le chutier|La clip pulita è renderizzata: è nel contenitore media|クリーンなクリップをレンダーしました：メディアビンにあります|깨끗한 클립이 렌더되었습니다: 미디어 빈에 있습니다|O clipe limpo foi renderizado: está na caixa de mídia|Чистый клип готов: он в корзине медиа|Temiz klip oluşturuldu: medya kutusunda|干净剪辑已渲染：在媒体箱中|乾淨片段已算繪：在媒體庫中
Applied to this clip|Appliqué à ce clip|Applicato a questa clip|このクリップに適用しました|이 클립에 적용했습니다|Aplicado a este clipe|Применено к этому клипу|Bu klibe uygulandı|已应用于此剪辑|已套用至此片段
Remove Stabilize / ReOrient / Lens|Retirer Stabiliser / Réorienter / Objectif|Rimuovi Stabilizza / Riorienta / Obiettivo|安定化 / 再配置 / レンズを解除|안정화 / 재배치 / 렌즈 제거|Remover Estabilizar / Reorientar / Lente|Убрать стабилизацию / разворот / объектив|Sabitle / Yeniden yönlendir / Lens kaldır|移除稳定 / 重新定向 / 镜头|移除穩定 / 重新定向 / 鏡頭
Lens: redistort|Objectif : redistordre|Obiettivo: ridistorci|レンズ：再歪曲|렌즈: 다시 왜곡|Lente: redistorcer|Объектив: вернуть искажение|Lens: yeniden bozun|镜头：重新畸变|鏡頭：重新畸變
Lens lines: draw freehand along edges that should be straight|Lignes d'objectif : tracez à main levée le long des bords qui devraient être droits|Linee obiettivo: disegna a mano libera lungo bordi che dovrebbero essere dritti|レンズライン：本来まっすぐな輪郭に沿ってフリーハンドで描く|렌즈 선: 곧아야 할 가장자리를 따라 자유롭게 그리기|Linhas de lente: desenhe à mão livre ao longo de bordas que deveriam ser retas|Линии объектива: рисуйте от руки вдоль краёв, которые должны быть прямыми|Lens çizgileri: düz olması gereken kenarlar boyunca serbest çizin|镜头线：沿应为直线的边缘手绘|鏡頭線：沿應為直線的邊緣手繪
Solve lens|Calculer l'objectif|Calcola obiettivo|レンズを算出|렌즈 계산|Calcular lente|Рассчитать объектив|Lensi hesapla|计算镜头|計算鏡頭
Clear lens lines|Effacer les lignes d'objectif|Cancella linee obiettivo|レンズラインを消去|렌즈 선 지우기|Limpar linhas de lente|Очистить линии объектива|Lens çizgilerini temizle|清除镜头线|清除鏡頭線
Draw two or more lens lines along straight edges first|Tracez d'abord au moins deux lignes d'objectif le long de bords droits|Disegna prima due o più linee obiettivo lungo bordi dritti|まず直線の輪郭に沿ってレンズラインを2本以上描いてください|먼저 곧은 가장자리를 따라 렌즈 선을 두 개 이상 그리세요|Desenhe primeiro duas ou mais linhas de lente ao longo de bordas retas|Сначала нарисуйте две или более линии объектива вдоль прямых краёв|Önce düz kenarlar boyunca iki veya daha fazla lens çizgisi çizin|请先沿直边画两条或更多镜头线|請先沿直邊畫兩條或更多鏡頭線
Lens solved: this clip is undistorted|Objectif calculé : ce clip est corrigé|Obiettivo calcolato: questa clip è corretta|レンズを算出しました：このクリップの歪みを補正しました|렌즈 계산 완료: 이 클립의 왜곡을 보정했습니다|Lente calculada: este clipe foi corrigido|Объектив рассчитан: искажение клипа исправлено|Lens hesaplandı: bu klibin bozulması düzeltildi|镜头已计算：此剪辑已校正畸变|鏡頭已計算：此片段已校正畸變
Following the shape through the shot…|Suivi de la forme dans le plan…|Inseguimento della forma nell'inquadratura…|ショット全体で形状を追跡中…|샷 전체에서 모양을 따라가는 중…|Seguindo a forma ao longo do plano…|Отслеживание формы по всему плану…|Şekil çekim boyunca izleniyor…|正在整个镜头中跟随形状…|正在整個鏡頭中跟隨形狀…
The shape is keyed on every frame to the end of the shot|La forme a une clé sur chaque image jusqu'à la fin du plan|La forma ha una chiave su ogni fotogramma fino alla fine dell'inquadratura|ショットの終わりまで全フレームで形状にキーを設定しました|샷 끝까지 모든 프레임에 모양 키가 설정되었습니다|A forma tem chave em todos os quadros até o fim do plano|Форма получила ключ на каждом кадре до конца плана|Şekil çekimin sonuna kadar her karede anahtarlandı|形状已在每一帧上设置关键帧，直至镜头结束|形狀已在每一影格設定關鍵影格，直到鏡頭結束
No faces found on this frame|Aucun visage trouvé sur cette image|Nessun volto trovato in questo fotogramma|このフレームに顔は見つかりませんでした|이 프레임에서 얼굴을 찾지 못했습니다|Nenhum rosto encontrado neste quadro|На этом кадре лица не найдены|Bu karede yüz bulunamadı|此帧未找到人脸|此影格未找到人臉
The layer is now the clip's own tracked mask|Le calque est maintenant le masque suivi du clip|Il livello è ora la maschera tracciata della clip|レイヤーがクリップ自身のトラッキングマスクになりました|레이어가 이제 클립 자체의 트래킹 마스크입니다|A camada agora é a máscara rastreada do próprio clipe|Слой теперь стал отслеживаемой маской клипа|Katman artık klibin kendi izlenen maskesi|该图层现在是剪辑自己的跟踪蒙版|此圖層現在是片段自己的追蹤遮罩
Copy track data|Copier les données de suivi|Copia dati di tracciamento|トラッキングデータをコピー|트래킹 데이터 복사|Copiar dados de rastreamento|Копировать данные трекинга|İzleme verilerini kopyala|复制跟踪数据|複製追蹤資料
Track data copied: paste it into the host it was made for|Données de suivi copiées : collez-les dans le logiciel visé|Dati di tracciamento copiati: incollali nel programma a cui sono destinati|トラッキングデータをコピーしました：対象のソフトに貼り付けてください|트래킹 데이터를 복사했습니다: 대상 프로그램에 붙여 넣으세요|Dados de rastreamento copiados: cole-os no programa a que se destinam|Данные трекинга скопированы: вставьте их в программу, для которой они сделаны|İzleme verileri kopyalandı: hazırlandığı programa yapıştırın|已复制跟踪数据：粘贴到目标软件中|已複製追蹤資料：貼到目標軟體中
Move in front|Mettre devant|Porta davanti|前面へ移動|앞으로 이동|Trazer para frente|Переместить вперёд|Öne taşı|移到前面|移到前面
Delete layer|Supprimer le calque|Elimina livello|レイヤーを削除|레이어 삭제|Excluir camada|Удалить слой|Katmanı sil|删除图层|刪除圖層
Draw a shape around a flat surface to track: a screen, a sign, a wall|Dessinez une forme autour d'une surface plane : un écran, un panneau, un mur|Disegna una forma attorno a una superficie piana: uno schermo, un cartello, un muro|平らな面を囲むシェイプを描きます：画面、看板、壁|평평한 면을 둘러싸는 셰이프를 그리세요: 화면, 간판, 벽|Desenhe uma forma em volta de uma superfície plana: uma tela, uma placa, uma parede|Нарисуйте фигуру вокруг плоской поверхности: экрана, вывески, стены|Düz bir yüzeyin çevresine şekil çizin: ekran, tabela, duvar|围绕要跟踪的平面绘制形状：屏幕、招牌、墙面|圍繞要追蹤的平面繪製形狀：螢幕、招牌、牆面
Layer|Calque|Livello|レイヤー|레이어|Camada|Слой|Katman|图层|圖層
Changing a tracked layer's shapes or settings starts its track afresh. Go ahead?|Modifier les formes ou les réglages d'un calque suivi recommence son suivi. Continuer ?|Cambiare le forme o le impostazioni di un livello tracciato ne ricomincia il tracciamento. Procedere?|トラッキング済みレイヤーのシェイプや設定を変えると、トラッキングはやり直しになります。続けますか？|트래킹된 레이어의 셰이프나 설정을 바꾸면 트래킹이 처음부터 다시 시작됩니다. 계속할까요?|Alterar as formas ou ajustes de uma camada rastreada reinicia o rastreamento. Continuar?|Изменение фигур или настроек отслеженного слоя начинает трекинг заново. Продолжить?|İzlenmiş bir katmanın şekillerini veya ayarlarını değiştirmek izlemeyi baştan başlatır. Devam edilsin mi?|更改已跟踪图层的形状或设置会让跟踪重新开始。继续吗？|變更已追蹤圖層的形狀或設定會讓追蹤重新開始。要繼續嗎？
Delete this layer and its track?|Supprimer ce calque et son suivi ?|Eliminare questo livello e il suo tracciamento?|このレイヤーとトラッキングを削除しますか？|이 레이어와 트래킹을 삭제할까요?|Excluir esta camada e seu rastreamento?|Удалить этот слой и его трекинг?|Bu katman ve izi silinsin mi?|删除此图层及其跟踪？|刪除此圖層及其追蹤？
Auto|Auto|Auto|自動|자동|Auto|Авто|Otomatik|自动|自動
Translation|Translation|Traslazione|位置|이동|Translação|Смещение|Öteleme|平移|平移
Shear|Cisaillement|Inclinazione|シアー|기울이기|Cisalhamento|Сдвиг|Eğme|错切|錯切
Perspective|Perspective|Prospettiva|パース|원근|Perspectiva|Перспектива|Perspektif|透视|透視
Input channel|Canal d'entrée|Canale di ingresso|入力チャンネル|입력 채널|Canal de entrada|Входной канал|Giriş kanalı|输入通道|輸入通道
Luminance|Luminance|Luminanza|輝度|휘도|Luminância|Яркость|Parlaklık|亮度|亮度
Auto channel|Canal automatique|Canale automatico|自動チャンネル|자동 채널|Canal automático|Авто-канал|Otomatik kanal|自动通道|自動通道
Min % pixels used|% min. de pixels utilisés|% min. di pixel usati|使用ピクセルの最小 %|사용 픽셀 최소 %|% mín. de pixels usados|Мин. % используемых пикселей|Kullanılan en az piksel %|最小像素使用率 %|最小像素使用率 %
Smoothing level|Niveau de lissage|Livello di smussatura|スムージング|스무딩 수준|Nível de suavização|Уровень сглаживания|Yumuşatma düzeyi|平滑级别|平滑等級
Large motion|Grand mouvement|Movimento ampio|大きな動き|큰 움직임|Movimento grande|Большое движение|Büyük hareket|大幅运动|大幅運動
Small motion|Petit mouvement|Movimento piccolo|小さな動き|작은 움직임|Movimento pequeno|Малое движение|Küçük hareket|小幅运动|小幅運動
Manual|Manuel|Manuale|手動|수동|Manual|Вручную|Elle|手动|手動
Search area|Zone de recherche|Area di ricerca|検索範囲|검색 영역|Área de busca|Область поиска|Arama alanı|搜索区域|搜尋區域
Zoom %|Zoom %|Zoom %|ズーム %|확대 %|Zoom %|Зум %|Yakınlaştırma %|缩放 %|縮放 %
Go to the layer's reference frame or a tracked frame|Allez à l'image de référence du calque ou à une image suivie|Vai al fotogramma di riferimento del livello o a uno tracciato|レイヤーの基準フレームかトラッキング済みフレームへ移動してください|레이어의 기준 프레임이나 트래킹된 프레임으로 이동하세요|Vá ao quadro de referência da camada ou a um quadro rastreado|Перейдите к опорному кадру слоя или к отслеженному кадру|Katmanın referans karesine veya izlenmiş bir kareye gidin|请转到图层的参考帧或已跟踪的帧|請移到圖層的參考影格或已追蹤的影格
Draw a shape on the layer first|Dessinez d'abord une forme sur le calque|Disegna prima una forma sul livello|まずレイヤーにシェイプを描いてください|먼저 레이어에 셰이프를 그리세요|Desenhe primeiro uma forma na camada|Сначала нарисуйте фигуру на слое|Önce katmana bir şekil çizin|请先在图层上绘制形状|請先在圖層上繪製形狀
Tracking frame|Suivi de l'image|Tracciamento del fotogramma|フレームをトラッキング中|프레임 트래킹 중|Rastreando o quadro|Трекинг кадра|Kare izleniyor|正在跟踪帧|正在追蹤影格
Frames tracked:|Images suivies :|Fotogrammi tracciati:|トラッキングしたフレーム:|트래킹한 프레임:|Quadros rastreados:|Отслежено кадров:|İzlenen kareler:|已跟踪帧数：|已追蹤影格：
This clip's media cannot be read|Le média de ce clip est illisible|Il media di questa clip non è leggibile|このクリップのメディアを読み込めません|이 클립의 미디어를 읽을 수 없습니다|A mídia deste clipe não pode ser lida|Медиа этого клипа не читается|Bu klibin medyası okunamıyor|无法读取此片段的媒体|無法讀取此片段的媒體
Track surface…|Suivre une surface…|Traccia superficie…|サーフェスをトラッキング…|서피스 트래킹…|Rastrear superfície…|Трекинг поверхности…|Yüzey izle…|跟踪平面…|追蹤平面…
Select a video clip to track|Sélectionnez un clip vidéo à suivre|Seleziona una clip video da tracciare|トラッキングするビデオクリップを選んでください|트래킹할 비디오 클립을 선택하세요|Selecione um clipe de vídeo para rastrear|Выберите видеоклип для трекинга|İzlemek için bir video klibi seçin|请选择要跟踪的视频片段|請選取要追蹤的影片片段
Prompt wrap|Suite de prompts|Sequenza di prompt|プロンプトラップ|프롬프트 랩|Sequência de prompts|Набор запросов|İstem dizisi|提示词序列|提示詞序列
Runs a prompt-wrap.json on its own: each entry's prompt, size, steps, seed and LoRAs, nothing from the settings above|Exécute un prompt-wrap.json seul : le prompt, la taille, les étapes, la graine et les LoRA de chaque entrée, rien des réglages ci-dessus|Esegue un prompt-wrap.json da solo: prompt, dimensioni, passi, seed e LoRA di ogni voce, nulla delle impostazioni sopra|prompt-wrap.json を単独で実行します：各項目のプロンプト、サイズ、ステップ、シード、LoRA を使い、上の設定は使いません|prompt-wrap.json을 단독으로 실행합니다. 각 항목의 프롬프트, 크기, 단계, 시드, LoRA를 쓰며 위의 설정은 쓰지 않습니다|Executa um prompt-wrap.json sozinho: prompt, tamanho, passos, semente e LoRAs de cada entrada, nada dos ajustes acima|Запускает prompt-wrap.json сам по себе: запрос, размер, шаги, сид и LoRA каждой записи, ничего из настроек выше|Bir prompt-wrap.json'ı tek başına çalıştırır: her girdinin istemi, boyutu, adımları, tohumu ve LoRA'ları; yukarıdaki ayarlardan hiçbir şey|单独运行 prompt-wrap.json：使用每个条目的提示词、尺寸、步数、种子和 LoRA，不使用上面的任何设置|單獨執行 prompt-wrap.json：使用每個項目的提示詞、尺寸、步數、種子和 LoRA，不使用上面的任何設定
Run wrap|Lancer la suite|Esegui sequenza|ラップを実行|랩 실행|Executar sequência|Запустить набор|Diziyi çalıştır|运行序列|執行序列
Round and round|En boucle|A ciclo continuo|繰り返す|계속 반복|Em ciclo|По кругу|Döngüde|循环往复|循環往復
Load a prompt wrap first|Chargez d’abord une suite de prompts|Carica prima una sequenza di prompt|先にプロンプトラップを読み込んでください|먼저 프롬프트 랩을 불러오세요|Carregue primeiro uma sequência de prompts|Сначала загрузите набор запросов|Önce bir istem dizisi yükleyin|请先载入提示词序列|請先載入提示詞序列
A prompt wrap runs with Krea 2 and its checkpoints: choose one of them|Une suite de prompts fonctionne avec Krea 2 et ses checkpoints : choisissez-en un|Una sequenza di prompt funziona con Krea 2 e i suoi checkpoint: scegline uno|プロンプトラップは Krea 2 とそのチェックポイントで動作します。いずれかを選んでください|프롬프트 랩은 Krea 2와 그 체크포인트에서 실행됩니다. 그중 하나를 선택하세요|Uma sequência de prompts roda com o Krea 2 e seus checkpoints: escolha um deles|Набор запросов работает с Krea 2 и его чекпойнтами: выберите один из них|İstem dizisi Krea 2 ve checkpoint'leriyle çalışır: birini seçin|提示词序列需使用 Krea 2 及其检查点运行：请选择其一|提示詞序列需使用 Krea 2 及其檢查點執行：請選擇其一
Kept in the generative library; Add to media puts one on hand for the timeline|Conservé dans la bibliothèque générative ; Ajouter aux médias en rend un disponible pour la timeline|Conservate nella libreria generativa; Aggiungi ai media ne rende una disponibile per la timeline|生成ライブラリに保存されます。「メディアに追加」でタイムライン用に使えます|생성 라이브러리에 보관됩니다. 미디어에 추가하면 타임라인에서 쓸 수 있습니다|Mantidas na biblioteca generativa; Adicionar à mídia deixa uma pronta para a linha do tempo|Хранятся в библиотеке генераций; «Добавить в медиа» делает одну доступной для таймлайна|Üretim kitaplığında tutulur; Medyaya ekle birini zaman çizelgesi için hazırlar|保存在生成库中；“添加到媒体”可将其用于时间线|保存在生成庫中；「加入媒體」可將其用於時間軸
Show older|Afficher les plus anciens|Mostra i precedenti|古いものを表示|이전 항목 보기|Mostrar anteriores|Показать старые|Eskileri göster|显示更早的|顯示更早的
Add to media|Ajouter aux médias|Aggiungi ai media|メディアに追加|미디어에 추가|Adicionar à mídia|Добавить в медиа|Medyaya ekle|添加到媒体|加入媒體
Added to the media library|Ajouté à la médiathèque|Aggiunto alla libreria media|メディアライブラリに追加しました|미디어 라이브러리에 추가됨|Adicionado à biblioteca de mídia|Добавлено в медиатеку|Medya kitaplığına eklendi|已添加到媒体库|已加入媒體庫
Delete this generation?|Supprimer cette génération ?|Eliminare questa generazione?|この生成物を削除しますか？|이 생성물을 삭제할까요?|Excluir esta geração?|Удалить эту генерацию?|Bu üretim silinsin mi?|删除这个生成结果？|刪除這個生成結果？
Load prompt wrap…|Charger une suite de prompts…|Carica sequenza di prompt…|プロンプトラップを読み込む…|프롬프트 랩 불러오기…|Carregar sequência de prompts…|Загрузить набор запросов…|İstem dizisi yükle…|载入提示词序列…|載入提示詞序列…
Clear|Effacer|Cancella|クリア|지우기|Limpar|Очистить|Temizle|清除|清除
{file}: {n} prompts, in turn|{file} : {n} prompts, tour à tour|{file}: {n} prompt, a turno|{file}：{n} 個のプロンプトを順番に|{file}: 프롬프트 {n}개를 차례로|{file}: {n} prompts, em sequência|{file}: {n} запросов по очереди|{file}: {n} istem, sırayla|{file}：{n} 个提示词，依次使用|{file}：{n} 個提示詞，依序使用
That file is not JSON|Ce fichier n’est pas du JSON|Quel file non è JSON|そのファイルは JSON ではありません|그 파일은 JSON이 아닙니다|Esse arquivo não é JSON|Этот файл не в формате JSON|Bu dosya JSON değil|该文件不是 JSON|該檔案不是 JSON
Generation|Génération|Generazione|生成物|생성물|Geração|Генерация|Üretim|生成结果|生成結果
Cloud|Cloud|Cloud|クラウド|클라우드|Nuvem|Облако|Bulut|云端|雲端
Collect files…|Rassembler les fichiers…|Raccogli file…|ファイルを収集…|파일 모으기…|Reunir arquivos…|Собрать файлы…|Dosyaları topla…|收集文件…|收集檔案…
Collecting files…|Rassemblement des fichiers…|Raccolta dei file…|ファイルを収集しています…|파일을 모으는 중…|Reunindo arquivos…|Сбор файлов…|Dosyalar toplanıyor…|正在收集文件…|正在收集檔案…
Collected into|Rassemblé dans|Raccolto in|収集先|모은 위치|Reunido em|Собрано в|Toplandı:|已收集到|已收集至
Open project file…|Ouvrir un fichier de projet…|Apri file di progetto…|プロジェクトファイルを開く…|프로젝트 파일 열기…|Abrir arquivo de projeto…|Открыть файл проекта…|Proje dosyası aç…|打开项目文件…|開啟專案檔…
Save as project file…|Enregistrer comme fichier de projet…|Salva come file di progetto…|プロジェクトファイルとして保存…|프로젝트 파일로 저장…|Salvar como arquivo de projeto…|Сохранить как файл проекта…|Proje dosyası olarak kaydet…|另存为项目文件…|另存為專案檔…
Saved to|Enregistré dans|Salvato in|保存先|저장 위치|Salvo em|Сохранено в|Kaydedildi:|已保存到|已儲存至
Project opened|Projet ouvert|Progetto aperto|プロジェクトを開きました|프로젝트를 열었습니다|Projeto aberto|Проект открыт|Proje açıldı|项目已打开|專案已開啟
Missing media|Médias manquants|Media mancanti|見つからないメディア|누락된 미디어|Mídia ausente|Отсутствующие медиафайлы|Eksik medya|缺失的媒体|遺失的媒體
These files are not where the project last found them. Locate one, or search a folder: the others are looked for there too.|Ces fichiers ne sont plus là où le projet les a trouvés la dernière fois. Localisez-en un ou cherchez dans un dossier : les autres y sont cherchés aussi.|Questi file non sono più dove il progetto li ha trovati l’ultima volta. Trovane uno o cerca in una cartella: gli altri vengono cercati anche lì.|これらのファイルは、プロジェクトが最後に見つけた場所にありません。1つを探すか、フォルダを検索してください。ほかのファイルもそこで探します。|이 파일들은 프로젝트가 마지막으로 찾은 위치에 없습니다. 하나를 찾거나 폴더를 검색하세요. 나머지도 그곳에서 찾습니다.|Estes arquivos não estão onde o projeto os encontrou pela última vez. Localize um ou procure em uma pasta: os outros também são procurados lá.|Этих файлов нет там, где проект нашёл их в последний раз. Найдите один или выполните поиск в папке: остальные тоже будут искаться там.|Bu dosyalar, projenin onları en son bulduğu yerde değil. Birini bulun ya da bir klasörde arayın: diğerleri de orada aranır.|这些文件不在项目上次找到它们的位置。找到其中一个，或搜索一个文件夹：其余的也会在那里查找。|這些檔案不在專案上次找到它們的位置。找到其中一個，或搜尋一個資料夾：其餘的也會在那裡尋找。
Locate…|Localiser…|Trova…|探す…|찾기…|Localizar…|Найти…|Bul…|定位…|定位…
Search a folder…|Chercher dans un dossier…|Cerca in una cartella…|フォルダを検索…|폴더 검색…|Procurar em uma pasta…|Искать в папке…|Bir klasörde ara…|搜索文件夹…|搜尋資料夾…
Done|Terminé|Fatto|完了|완료|Concluído|Готово|Bitti|完成|完成
{n} found; the rest are still missing|{n} trouvés ; les autres manquent encore|{n} trovati; gli altri mancano ancora|{n} 件見つかりました。残りはまだ見つかりません|{n}개를 찾았습니다. 나머지는 아직 없습니다|{n} encontrados; o restante ainda está ausente|Найдено: {n}; остальные всё ещё отсутствуют|{n} bulundu; kalanlar hâlâ eksik|找到 {n} 个；其余仍缺失|找到 {n} 個；其餘仍遺失
Every file is found|Tous les fichiers sont trouvés|Tutti i file sono stati trovati|すべてのファイルが見つかりました|모든 파일을 찾았습니다|Todos os arquivos foram encontrados|Все файлы найдены|Tüm dosyalar bulundu|所有文件都已找到|所有檔案都已找到
Searching…|Recherche…|Ricerca…|検索中…|검색 중…|Procurando…|Поиск…|Aranıyor…|正在搜索…|正在搜尋…
Use it anyway?|L’utiliser quand même ?|Usarlo comunque?|それでも使いますか？|그래도 사용하시겠습니까?|Usar mesmo assim?|Всё равно использовать?|Yine de kullanılsın mı?|仍然使用吗？|仍要使用嗎？
Stopped|Arrêté|Fermato|停止しました|중지됨|Parado|Остановлено|Durduruldu|已停止|已停止
Finishing this picture, then stopping|Fin de cette image, puis arrêt|Completa questa immagine, poi si ferma|この画像を仕上げてから停止します|이 이미지를 마친 뒤 중지합니다|Terminando esta imagem e depois parando|Завершается это изображение, затем остановка|Bu görsel tamamlanıyor, sonra durulacak|完成这张图片后停止|完成這張圖片後停止
Continuous: {n} pictures, the model kept loaded|En continu : {n} images, le modèle reste chargé|Continuo: {n} immagini, il modello resta caricato|連続：{n} 枚、モデルは読み込まれたまま|연속: {n}장, 모델은 로드된 상태 유지|Contínuo: {n} imagens, o modelo continua carregado|Непрерывно: {n} изображений, модель остаётся загруженной|Sürekli: {n} görsel, model yüklü kalıyor|连续：{n} 张图片，模型保持加载|連續：{n} 張圖片，模型保持載入
Stopped after {n} pictures|Arrêté après {n} images|Fermato dopo {n} immagini|{n} 枚で停止しました|{n}장 후 중지됨|Parado após {n} imagens|Остановлено после {n} изображений|{n} görselden sonra durduruldu|在 {n} 张图片后停止|在 {n} 張圖片後停止
The next picture uses the new prompt|L’image suivante utilise le nouveau prompt|L’immagine successiva usa il nuovo prompt|次の画像から新しいプロンプトを使います|다음 이미지부터 새 프롬프트를 사용합니다|A próxima imagem usa o novo prompt|Следующее изображение использует новый запрос|Sonraki görsel yeni istemi kullanır|下一张图片使用新的提示词|下一張圖片使用新的提示詞
Steps|Étapes|Passi|ステップ数|단계|Passos|Шаги|Adımlar|步数|步數
Seed|Graine|Seed|シード|시드|Semente|Сид|Tohum|种子|種子
-1 is a random seed; the seed used is shown with each picture and written into its file|-1 est une graine aléatoire ; la graine utilisée s’affiche avec chaque image et est écrite dans son fichier|-1 è un seed casuale; il seed usato è mostrato con ogni immagine e scritto nel suo file|-1 はランダムなシードです。使われたシードは各画像に表示され、ファイルにも書き込まれます|-1은 무작위 시드입니다. 사용된 시드는 각 이미지와 함께 표시되고 파일에 기록됩니다|-1 é uma semente aleatória; a semente usada aparece com cada imagem e é gravada no arquivo dela|-1 — случайный сид; использованный сид показывается у каждого изображения и записывается в его файл|-1 rastgele tohumdur; kullanılan tohum her görselle gösterilir ve dosyasına yazılır|-1 表示随机种子；所用种子会显示在每张图片旁并写入其文件|-1 表示隨機種子；所用種子會顯示在每張圖片旁並寫入其檔案
Random|Aléatoire|Casuale|ランダム|무작위|Aleatória|Случайный|Rastgele|随机|隨機
Continuous|En continu|Continuo|連続|연속|Contínuo|Непрерывно|Sürekli|连续|連續
continuous, run {n}|en continu, passage {n}|continuo, esecuzione {n}|連続、{n} 回目|연속, {n}회째|contínuo, execução {n}|непрерывно, запуск {n}|sürekli, {n}. çalıştırma|连续，第 {n} 次|連續，第 {n} 次
Krea 2 Turbo (optional)|Krea 2 Turbo (facultatif)|Krea 2 Turbo (facoltativo)|Krea 2 Turbo（オプション）|Krea 2 Turbo (선택)|Krea 2 Turbo (opcional)|Krea 2 Turbo (необязательно)|Krea 2 Turbo (isteğe bağlı)|Krea 2 Turbo（可选）|Krea 2 Turbo（選用）
A 12-billion-parameter image model from Krea, run on this computer. Nothing is downloaded until you install it here.|Un modèle d’image de Krea à 12 milliards de paramètres, exécuté sur cet ordinateur. Rien n’est téléchargé tant que vous ne l’installez pas ici.|Un modello di immagini di Krea da 12 miliardi di parametri, eseguito su questo computer. Non viene scaricato nulla finché non lo installi qui.|Krea の 120 億パラメータの画像モデルで、このコンピュータ上で動作します。ここでインストールするまで何もダウンロードされません。|Krea의 120억 매개변수 이미지 모델로, 이 컴퓨터에서 실행됩니다. 여기에서 설치하기 전에는 아무것도 다운로드되지 않습니다.|Um modelo de imagem da Krea com 12 bilhões de parâmetros, executado neste computador. Nada é baixado até você instalá-lo aqui.|Модель изображений Krea на 12 миллиардов параметров, работающая на этом компьютере. Ничего не загружается, пока вы не установите её здесь.|Krea'nın 12 milyar parametreli görsel modeli, bu bilgisayarda çalışır. Buradan yükleyene kadar hiçbir şey indirilmez.|Krea 的 120 亿参数图像模型，在这台电脑上运行。在这里安装之前不会下载任何内容。|Krea 的 120 億參數影像模型，在這台電腦上執行。在這裡安裝之前不會下載任何內容。
Read the full agreement|Lire l’accord complet|Leggi l’accordo completo|契約の全文を読む|계약 전문 읽기|Ler o acordo completo|Прочитать соглашение полностью|Sözleşmenin tamamını oku|阅读完整协议|閱讀完整協議
Acceptable Use Policy|Politique d’utilisation acceptable|Norme di utilizzo accettabile|利用規定|허용되는 사용 정책|Política de uso aceitável|Правила допустимого использования|Kabul Edilebilir Kullanım Politikası|可接受使用政策|可接受使用政策
I have read and accept the Krea 2 Community License Agreement|J’ai lu et j’accepte le Krea 2 Community License Agreement|Ho letto e accetto il Krea 2 Community License Agreement|Krea 2 Community License Agreement を読み、同意します|Krea 2 Community License Agreement를 읽었으며 이에 동의합니다|Li e aceito o Krea 2 Community License Agreement|Я прочитал(а) и принимаю Krea 2 Community License Agreement|Krea 2 Community License Agreement'ı okudum ve kabul ediyorum|我已阅读并接受 Krea 2 Community License Agreement|我已閱讀並接受 Krea 2 Community License Agreement
Content filter, installed with Krea 2|Filtre de contenu, installé avec Krea 2|Filtro dei contenuti, installato con Krea 2|コンテンツフィルター（Krea 2 と一緒にインストール）|콘텐츠 필터 (Krea 2와 함께 설치)|Filtro de conteúdo, instalado com o Krea 2|Фильтр содержимого, устанавливается с Krea 2|İçerik filtresi, Krea 2 ile yüklenir|内容过滤器，随 Krea 2 安装|內容過濾器，隨 Krea 2 安裝
Build|Version|Versione|ビルド|빌드|Versão|Сборка|Sürüm|版本|版本
Install Krea 2|Installer Krea 2|Installa Krea 2|Krea 2 をインストール|Krea 2 설치|Instalar o Krea 2|Установить Krea 2|Krea 2'yi yükle|安装 Krea 2|安裝 Krea 2
Generate with Krea 2|Générer avec Krea 2|Genera con Krea 2|Krea 2 で生成|Krea 2로 생성|Gerar com o Krea 2|Создать с Krea 2|Krea 2 ile üret|用 Krea 2 生成|用 Krea 2 生成
No Krea 2 build for this computer|Aucune version de Krea 2 pour cet ordinateur|Nessuna versione di Krea 2 per questo computer|このコンピュータ向けの Krea 2 ビルドはありません|이 컴퓨터용 Krea 2 빌드가 없습니다|Nenhuma versão do Krea 2 para este computador|Нет сборки Krea 2 для этого компьютера|Bu bilgisayar için Krea 2 sürümü yok|没有适用于这台电脑的 Krea 2 版本|沒有適用於這台電腦的 Krea 2 版本
Krea 2 and its content filter are installed.|Krea 2 et son filtre de contenu sont installés.|Krea 2 e il suo filtro dei contenuti sono installati.|Krea 2 とコンテンツフィルターをインストールしました。|Krea 2와 콘텐츠 필터가 설치되었습니다.|O Krea 2 e seu filtro de conteúdo estão instalados.|Krea 2 и его фильтр содержимого установлены.|Krea 2 ve içerik filtresi yüklendi.|Krea 2 及其内容过滤器已安装。|Krea 2 及其內容過濾器已安裝。
The content filter is installed again and runs on every Krea 2 picture.|Le filtre de contenu est réinstallé et s’applique à chaque image de Krea 2.|Il filtro dei contenuti è di nuovo installato e controlla ogni immagine di Krea 2.|コンテンツフィルターを再インストールしました。Krea 2 のすべての画像に適用されます。|콘텐츠 필터가 다시 설치되어 모든 Krea 2 이미지에 적용됩니다.|O filtro de conteúdo foi reinstalado e se aplica a todas as imagens do Krea 2.|Фильтр содержимого снова установлен и проверяет каждое изображение Krea 2.|İçerik filtresi yeniden yüklendi ve her Krea 2 görselinde çalışıyor.|内容过滤器已重新安装，会处理每张 Krea 2 图片。|內容過濾器已重新安裝，會處理每張 Krea 2 圖片。
Installed|Installé|Installato|インストール済み|설치됨|Instalado|Установлено|Yüklendi|已安装|已安裝
Installed: {build}|Installé : {build}|Installato: {build}|インストール済み：{build}|설치됨: {build}|Instalado: {build}|Установлено: {build}|Yüklendi: {build}|已安装：{build}|已安裝：{build}
content filter on|filtre de contenu actif|filtro dei contenuti attivo|コンテンツフィルター有効|콘텐츠 필터 켜짐|filtro de conteúdo ativo|фильтр содержимого включён|içerik filtresi açık|内容过滤器已开启|內容過濾器已開啟
content filter removed|filtre de contenu retiré|filtro dei contenuti rimosso|コンテンツフィルター削除済み|콘텐츠 필터 제거됨|filtro de conteúdo removido|фильтр содержимого удалён|içerik filtresi kaldırıldı|内容过滤器已移除|內容過濾器已移除
Not ready: {reason}|Pas prêt : {reason}|Non pronto: {reason}|準備未完了：{reason}|준비되지 않음: {reason}|Não está pronto: {reason}|Не готово: {reason}|Hazır değil: {reason}|未就绪：{reason}|未就緒：{reason}
Reinstall the content filter|Réinstaller le filtre de contenu|Reinstalla il filtro dei contenuti|コンテンツフィルターを再インストール|콘텐츠 필터 다시 설치|Reinstalar o filtro de conteúdo|Переустановить фильтр содержимого|İçerik filtresini yeniden yükle|重新安装内容过滤器|重新安裝內容過濾器
The content filter has been removed|Le filtre de contenu a été retiré|Il filtro dei contenuti è stato rimosso|コンテンツフィルターが削除されています|콘텐츠 필터가 제거되었습니다|O filtro de conteúdo foi removido|Фильтр содержимого удалён|İçerik filtresi kaldırıldı|内容过滤器已被移除|內容過濾器已被移除
I understand|J’ai compris|Ho capito|理解しました|이해했습니다|Entendi|Понятно|Anladım|我明白|我明白
FLUX.2 [klein] 4B (optional)|FLUX.2 [klein] 4B (facultatif)|FLUX.2 [klein] 4B (facoltativo)|FLUX.2 [klein] 4B（オプション）|FLUX.2 [klein] 4B (선택)|FLUX.2 [klein] 4B (opcional)|FLUX.2 [klein] 4B (необязательно)|FLUX.2 [klein] 4B (isteğe bağlı)|FLUX.2 [klein] 4B（可选）|FLUX.2 [klein] 4B（選用）
A 4-billion-parameter image model from Black Forest Labs, four steps a picture, under the Apache License 2.0 (commercial use allowed). Run on this computer through mflux, with LoRA stacks. Nothing is downloaded until you install it here.|Un modèle d’image de Black Forest Labs à 4 milliards de paramètres, quatre étapes par image, sous Apache License 2.0 (usage commercial autorisé). Exécuté sur cet ordinateur avec mflux, avec des piles de LoRA. Rien n’est téléchargé tant que vous ne l’installez pas ici.|Un modello di immagini di Black Forest Labs da 4 miliardi di parametri, quattro passi per immagine, con Apache License 2.0 (uso commerciale consentito). Eseguito su questo computer tramite mflux, con pile di LoRA. Non viene scaricato nulla finché non lo installi qui.|Black Forest Labs の 40 億パラメータの画像モデル。1 枚 4 ステップ、Apache License 2.0（商用利用可）。mflux でこのコンピュータ上で動作し、LoRA スタックを使えます。ここでインストールするまで何もダウンロードされません。|Black Forest Labs의 40억 매개변수 이미지 모델로, 이미지당 4단계이며 Apache License 2.0(상업적 사용 허용)을 따릅니다. mflux로 이 컴퓨터에서 실행되며 LoRA 스택을 사용할 수 있습니다. 여기에서 설치하기 전에는 아무것도 다운로드되지 않습니다.|Um modelo de imagem da Black Forest Labs com 4 bilhões de parâmetros, quatro passos por imagem, sob a Apache License 2.0 (uso comercial permitido). Executado neste computador pelo mflux, com pilhas de LoRA. Nada é baixado até você instalá-lo aqui.|Модель изображений Black Forest Labs на 4 миллиарда параметров, четыре шага на изображение, по лицензии Apache License 2.0 (коммерческое использование разрешено). Работает на этом компьютере через mflux, с наборами LoRA. Ничего не загружается, пока вы не установите её здесь.|Black Forest Labs'in 4 milyar parametreli görsel modeli; görsel başına dört adım, Apache License 2.0 altında (ticari kullanıma izin verilir). mflux ile bu bilgisayarda, LoRA yığınlarıyla çalışır. Buradan yükleyene kadar hiçbir şey indirilmez.|Black Forest Labs 的 40 亿参数图像模型，每张图四步，采用 Apache License 2.0（允许商业使用）。通过 mflux 在这台电脑上运行，可使用 LoRA 堆栈。在这里安装之前不会下载任何内容。|Black Forest Labs 的 40 億參數影像模型，每張圖四步，採用 Apache License 2.0（允許商業使用）。透過 mflux 在這台電腦上執行，可使用 LoRA 堆疊。在這裡安裝之前不會下載任何內容。
Read the model card and licence|Lire la fiche du modèle et la licence|Leggi la scheda del modello e la licenza|モデルカードとライセンスを読む|모델 카드와 라이선스 읽기|Ler a ficha do modelo e a licença|Прочитать карточку модели и лицензию|Model kartını ve lisansı oku|阅读模型卡和许可证|閱讀模型卡與授權
I have read the {licence} and accept it|J’ai lu la {licence} et je l’accepte|Ho letto la {licence} e la accetto|{licence} を読み、同意します|{licence}를 읽었으며 이에 동의합니다|Li a {licence} e a aceito|Я прочитал(а) {licence} и принимаю её|{licence} lisansını okudum ve kabul ediyorum|我已阅读并接受 {licence}|我已閱讀並接受 {licence}
Generate with it|Générer avec|Genera con questo|これで生成|이것으로 생성|Gerar com ele|Создать с ней|Bununla üret|用它生成|用它生成
{name} is installed.|{name} est installé.|{name} è installato.|{name} をインストールしました。|{name}이(가) 설치되었습니다.|{name} está instalado.|{name} установлен.|{name} yüklendi.|{name} 已安装。|{name} 已安裝。
Your own checkpoints|Vos propres checkpoints|I tuoi checkpoint|自分のチェックポイント|내 체크포인트|Seus próprios checkpoints|Ваши собственные чекпойнты|Kendi checkpoint'leriniz|你自己的检查点|你自己的檢查點
A Krea 2 or FLUX.2 [klein] 4B fine-tune converted to mflux's MLX format (the folder mflux-save writes: text_encoder/, tokenizer/, vae/ and the transformer's weights) runs here as a model of its own, with that model's LoRAs. Put each one's folder in:|Un fine-tuning de Krea 2 ou de FLUX.2 [klein] 4B converti au format MLX de mflux (le dossier écrit par mflux-save : text_encoder/, tokenizer/, vae/ et les poids du transformer) fonctionne ici comme un modèle à part entière, avec les LoRA de ce modèle. Placez le dossier de chacun dans :|Un fine-tuning di Krea 2 o FLUX.2 [klein] 4B convertito nel formato MLX di mflux (la cartella scritta da mflux-save: text_encoder/, tokenizer/, vae/ e i pesi del transformer) funziona qui come modello a sé, con le LoRA di quel modello. Metti la cartella di ciascuno in:|mflux の MLX 形式に変換した Krea 2 または FLUX.2 [klein] 4B のファインチューン（mflux-save が書き出すフォルダ：text_encoder/、tokenizer/、vae/ とトランスフォーマーの重み）は、ここで独立したモデルとして、そのモデルの LoRA と一緒に使えます。それぞれのフォルダを次の場所に置いてください：|mflux의 MLX 형식으로 변환한 Krea 2 또는 FLUX.2 [klein] 4B 파인튜닝(mflux-save가 만드는 폴더: text_encoder/, tokenizer/, vae/ 및 트랜스포머 가중치)은 여기에서 그 모델의 LoRA와 함께 독립된 모델로 실행됩니다. 각 폴더를 다음 위치에 넣으세요:|Um ajuste fino do Krea 2 ou do FLUX.2 [klein] 4B convertido para o formato MLX do mflux (a pasta que o mflux-save grava: text_encoder/, tokenizer/, vae/ e os pesos do transformer) funciona aqui como um modelo próprio, com as LoRAs desse modelo. Coloque a pasta de cada um em:|Дообученная версия Krea 2 или FLUX.2 [klein] 4B, преобразованная в формат MLX для mflux (папка, которую пишет mflux-save: text_encoder/, tokenizer/, vae/ и веса трансформера), работает здесь как отдельная модель с LoRA этой модели. Положите папку каждой в:|mflux'un MLX biçimine dönüştürülmüş bir Krea 2 veya FLUX.2 [klein] 4B ince ayarı (mflux-save'in yazdığı klasör: text_encoder/, tokenizer/, vae/ ve transformer ağırlıkları) burada o modelin LoRA'larıyla ayrı bir model olarak çalışır. Her birinin klasörünü şuraya koyun:|转换为 mflux MLX 格式的 Krea 2 或 FLUX.2 [klein] 4B 微调模型（mflux-save 写出的文件夹：text_encoder/、tokenizer/、vae/ 和 transformer 权重）会在这里作为独立模型运行，并可使用该模型的 LoRA。将每个模型的文件夹放在：|轉換為 mflux MLX 格式的 Krea 2 或 FLUX.2 [klein] 4B 微調模型（mflux-save 寫出的資料夾：text_encoder/、tokenizer/、vae/ 和 transformer 權重）會在這裡作為獨立模型執行，並可使用該模型的 LoRA。將每個模型的資料夾放在：
ready in the image generator|prêt dans le générateur d’images|pronto nel generatore di immagini|画像ジェネレーターで使用可能|이미지 생성기에서 사용 가능|pronto no gerador de imagens|готов в генераторе изображений|görsel üreticide hazır|已可在图像生成器中使用|已可在影像產生器中使用
{usable} of {total} usable|{usable} sur {total} utilisables|{usable} di {total} utilizzabili|{total} 件中 {usable} 件が使用可能|{total}개 중 {usable}개 사용 가능|{usable} de {total} utilizáveis|Можно использовать: {usable} из {total}|{total} içinden {usable} kullanılabilir|{total} 个中 {usable} 个可用|{total} 個中 {usable} 個可用
None yet|Aucun pour l’instant|Ancora nessuno|まだありません|아직 없음|Nenhum ainda|Пока нет|Henüz yok|还没有|還沒有
Start from|Partir de|Parti da|開始画像|시작 이미지|Partir de|Начать с|Başlangıç|起始于|起始於
Nothing (from the prompt alone)|Rien (le prompt seul)|Niente (solo il prompt)|なし（プロンプトのみ）|없음 (프롬프트만)|Nada (só o prompt)|Ничего (только запрос)|Hiçbir şey (yalnızca istem)|无（仅提示词）|無（僅提示詞）
The frame at the playhead|L’image sous la tête de lecture|Il fotogramma alla testina|再生ヘッドのフレーム|재생 헤드의 프레임|O quadro na agulha de reprodução|Кадр под курсором воспроизведения|Oynatma kafasındaki kare|播放头处的帧|播放頭處的影格
Image influence|Influence de l’image|Influenza dell’immagine|画像の影響度|이미지 영향|Influência da imagem|Влияние изображения|Görselin etkisi|图像影响|影像影響
Match the source picture|Comme l’image de départ|Come l’immagine di partenza|元画像に合わせる|원본 이미지에 맞춤|Igual à imagem de origem|Как у исходного изображения|Kaynak görsele uy|与源图像一致|與來源影像一致
Sampler|Échantillonneur|Campionatore|サンプラー|샘플러|Amostrador|Сэмплер|Örnekleyici|采样器|取樣器
Write <lora:name:strength> in the prompt as on Civitai (the name is the LoRA's file name), or paste a picture's generation data: its Steps, Seed, size and Model are used|Écrivez <lora:nom:intensité> dans le prompt comme sur Civitai (le nom est celui du fichier de la LoRA), ou collez les données de génération d’une image : ses Steps, Seed, taille et Model sont utilisés|Scrivi <lora:nome:intensità> nel prompt come su Civitai (il nome è quello del file della LoRA), oppure incolla i dati di generazione di un’immagine: si usano Steps, Seed, dimensione e Model|Civitai と同じくプロンプトに <lora:名前:強さ> と書くか（名前は LoRA のファイル名）、画像の生成データを貼り付けてください。Steps、Seed、サイズ、Model が使われます|Civitai처럼 프롬프트에 <lora:이름:강도>를 쓰거나(이름은 LoRA 파일 이름) 이미지의 생성 데이터를 붙여 넣으세요. Steps, Seed, 크기, Model이 사용됩니다|Escreva <lora:nome:intensidade> no prompt como no Civitai (o nome é o do arquivo da LoRA) ou cole os dados de geração de uma imagem: Steps, Seed, tamanho e Model são usados|Пишите <lora:имя:сила> в запросе, как на Civitai (имя — это имя файла LoRA), или вставьте данные генерации изображения: будут использованы его Steps, Seed, размер и Model|Civitai'deki gibi isteme <lora:ad:güç> yazın (ad, LoRA'nın dosya adıdır) ya da bir görselin üretim verilerini yapıştırın: Steps, Seed, boyut ve Model kullanılır|像在 Civitai 上一样在提示词中写 <lora:名称:强度>（名称即 LoRA 的文件名），或粘贴图片的生成数据：会使用其 Steps、Seed、尺寸和 Model|像在 Civitai 上一樣在提示詞中寫 <lora:名稱:強度>（名稱即 LoRA 的檔名），或貼上圖片的生成資料：會使用其 Steps、Seed、尺寸和 Model
Add from a link|Ajouter depuis un lien|Aggiungi da un link|リンクから追加|링크에서 추가|Adicionar de um link|Добавить по ссылке|Bağlantıdan ekle|从链接添加|從連結新增
No LoRAs for this model yet: drop .safetensors files into its folder, import one, or add one from a Hugging Face or Civitai link|Aucune LoRA pour ce modèle : déposez des fichiers .safetensors dans son dossier, importez-en un ou ajoutez-en une depuis un lien Hugging Face ou Civitai|Ancora nessuna LoRA per questo modello: metti file .safetensors nella sua cartella, importane uno o aggiungine una da un link Hugging Face o Civitai|このモデル用の LoRA はまだありません。.safetensors ファイルをフォルダに置くか、読み込むか、Hugging Face または Civitai のリンクから追加してください|이 모델용 LoRA가 아직 없습니다. .safetensors 파일을 폴더에 넣거나, 가져오거나, Hugging Face 또는 Civitai 링크에서 추가하세요|Ainda não há LoRAs para este modelo: coloque arquivos .safetensors na pasta dele, importe um ou adicione de um link do Hugging Face ou Civitai|Для этой модели пока нет LoRA: положите файлы .safetensors в её папку, импортируйте файл или добавьте по ссылке Hugging Face или Civitai|Bu model için henüz LoRA yok: .safetensors dosyalarını klasörüne bırakın, bir dosya içe aktarın veya Hugging Face ya da Civitai bağlantısından ekleyin|此模型还没有 LoRA：将 .safetensors 文件放入其文件夹、导入文件，或从 Hugging Face 或 Civitai 链接添加|此模型還沒有 LoRA：將 .safetensors 檔案放入其資料夾、匯入檔案，或從 Hugging Face 或 Civitai 連結新增
Or drop .safetensors files into|Ou déposez des fichiers .safetensors dans|Oppure metti file .safetensors in|または .safetensors ファイルをここに置く:|또는 .safetensors 파일을 여기에 넣기:|Ou coloque arquivos .safetensors em|Или положите файлы .safetensors в|Ya da .safetensors dosyalarını şuraya bırakın:|或将 .safetensors 文件放入|或將 .safetensors 檔案放入
Look again|Regarder à nouveau|Guarda di nuovo|再読み込み|다시 찾기|Verificar de novo|Проверить снова|Yeniden bak|重新查看|重新查看
Trigger words|Mots déclencheurs|Parole chiave|トリガーワード|트리거 단어|Palavras-gatilho|Слова-триггеры|Tetikleyici kelimeler|触发词|觸發詞
Memory|Mémoire|Memoria|メモリ|메모리|Memória|Память|Bellek|内存|記憶體
Low memory (slower)|Peu de mémoire (plus lent)|Poca memoria (più lento)|省メモリ（低速）|저메모리 (느림)|Pouca memória (mais lento)|Мало памяти (медленнее)|Düşük bellek (daha yavaş)|低内存（较慢）|低記憶體（較慢）
LoRAs|LoRA|LoRA|LoRA|LoRA|LoRAs|LoRA|LoRA'lar|LoRA|LoRA
Add LoRA|Ajouter une LoRA|Aggiungi LoRA|LoRA を追加|LoRA 추가|Adicionar LoRA|Добавить LoRA|LoRA ekle|添加 LoRA|新增 LoRA
Import a LoRA file|Importer un fichier LoRA|Importa un file LoRA|LoRA ファイルを読み込む|LoRA 파일 가져오기|Importar um arquivo LoRA|Импортировать файл LoRA|LoRA dosyası içe aktar|导入 LoRA 文件|匯入 LoRA 檔案
No LoRAs in this stack|Aucune LoRA dans cette pile|Nessuna LoRA in questa pila|このスタックに LoRA はありません|이 스택에 LoRA가 없습니다|Nenhuma LoRA nesta pilha|В этом наборе нет LoRA|Bu yığında LoRA yok|此堆栈中没有 LoRA|此堆疊中沒有 LoRA
Use this LoRA|Utiliser cette LoRA|Usa questa LoRA|この LoRA を使う|이 LoRA 사용|Usar esta LoRA|Использовать эту LoRA|Bu LoRA'yı kullan|使用此 LoRA|使用此 LoRA
Adding the LoRA|Ajout de la LoRA|Aggiunta della LoRA|LoRA を追加しています|LoRA 추가 중|Adicionando a LoRA|Добавление LoRA|LoRA ekleniyor|正在添加 LoRA|正在新增 LoRA
LoRA added|LoRA ajoutée|LoRA aggiunta|LoRA を追加しました|LoRA 추가됨|LoRA adicionada|LoRA добавлена|LoRA eklendi|已添加 LoRA|已新增 LoRA
Reveal word by word|Révéler mot par mot|Rivela parola per parola|一語ずつ表示|한 단어씩 나타내기|Revelar palavra por palavra|Показывать по одному слову|Kelime kelime göster|逐词显示|逐詞顯示
Rise the word|Faire monter le mot|Fai salire la parola|単語を浮き上がらせる|단어 떠오르기|Fazer a palavra subir|Слово поднимается|Kelimeyi yükselt|单词上浮|單詞上浮
Share this look|Partager ce style|Condividi questo stile|このスタイルを共有|이 스타일 공유|Compartilhar este estilo|Поделиться этим стилем|Bu stili paylaş|分享此样式|分享此樣式
Look name|Nom du style|Nome dello stile|スタイル名|스타일 이름|Nome do estilo|Название стиля|Stil adı|样式名称|樣式名稱
Your GitHub handle|Votre identifiant GitHub|Il tuo nome utente GitHub|GitHub のユーザー名|GitHub 사용자 이름|Seu usuário do GitHub|Ваше имя на GitHub|GitHub kullanıcı adınız|你的 GitHub 用户名|你的 GitHub 使用者名稱
Saves this look as a captions package: anyone can install it, and it is what you add to the community registry|Enregistre ce style comme paquet de sous-titres : tout le monde peut l’installer, et c’est ce que vous ajoutez au registre communautaire|Salva questo stile come pacchetto di sottotitoli: chiunque può installarlo, ed è ciò che aggiungi al registro della community|このスタイルを字幕パッケージとして保存します。誰でもインストールでき、コミュニティのレジストリに追加するのもこのファイルです|이 스타일을 자막 패키지로 저장합니다. 누구나 설치할 수 있으며, 커뮤니티 레지스트리에 추가하는 파일입니다|Salva este estilo como pacote de legendas: qualquer pessoa pode instalá-lo, e é o que você adiciona ao registro da comunidade|Сохраняет этот стиль как пакет субтитров: его может установить любой, и именно его вы добавляете в реестр сообщества|Bu stili altyazı paketi olarak kaydeder: herkes yükleyebilir ve topluluk kayıt defterine eklediğiniz dosya budur|将此样式保存为字幕包：任何人都可以安装，也是你添加到社区注册表的文件|將此樣式儲存為字幕套件：任何人都能安裝，也是你加入社群登錄庫的檔案
Look saved as|Style enregistré sous|Stile salvato come|スタイルの保存先|스타일 저장됨|Estilo salvo como|Стиль сохранён как|Stil şu adla kaydedildi|样式已保存为|樣式已儲存為
Could not share the look|Impossible de partager le style|Impossibile condividere lo stile|スタイルを共有できませんでした|스타일을 공유할 수 없습니다|Não foi possível compartilhar o estilo|Не удалось поделиться стилем|Stil paylaşılamadı|无法分享此样式|無法分享此樣式
Colour|Couleur|Colore|色|색상|Cor|Цвет|Renk|颜色|顏色
This computer has no H.264 encoder of its own, so this export uses Cisco's OpenH264, downloaded from Cisco (about 1 MB) the first time. Its licence and the switch are in Settings, Advanced.|Cet ordinateur n'a pas d'encodeur H.264 à lui, cet export utilise donc OpenH264 de Cisco, téléchargé chez Cisco (environ 1 Mo) la première fois. Sa licence et l'interrupteur sont dans Réglages, Avancé.|Questo computer non ha un codificatore H.264 proprio, quindi questa esportazione usa OpenH264 di Cisco, scaricato da Cisco (circa 1 MB) la prima volta. La licenza e l'interruttore sono in Impostazioni, Avanzate.|このコンピューターには H.264 エンコーダーがないため、この書き出しは Cisco の OpenH264 を使います。初回に Cisco から約 1 MB をダウンロードします。ライセンスとスイッチは設定の詳細にあります。|이 컴퓨터에는 자체 H.264 인코더가 없어 이 내보내기는 Cisco의 OpenH264를 사용하며, 처음 한 번 Cisco에서 약 1 MB를 내려받습니다. 라이선스와 스위치는 설정, 고급에 있습니다.|Este computador não tem codificador H.264 próprio, então esta exportação usa o OpenH264 da Cisco, baixado da Cisco (cerca de 1 MB) na primeira vez. A licença e o interruptor estão em Configurações, Avançado.|На этом компьютере нет собственного кодировщика H.264, поэтому этот экспорт использует OpenH264 от Cisco, который в первый раз загружается с сайта Cisco (около 1 МБ). Лицензия и переключатель находятся в Настройках, Дополнительно.|Bu bilgisayarın kendi H.264 kodlayıcısı yok, bu yüzden bu dışa aktarma Cisco'nun OpenH264'ünü kullanır; ilk seferinde Cisco'dan (yaklaşık 1 MB) indirilir. Lisansı ve anahtarı Ayarlar, Gelişmiş bölümündedir.|这台电脑没有自己的 H.264 编码器，因此此次导出使用 Cisco 的 OpenH264，首次会从 Cisco 下载（约 1 MB）。其许可证和开关在设置的高级中。|這台電腦沒有自己的 H.264 編碼器，因此此次匯出使用 Cisco 的 OpenH264，首次會從 Cisco 下載（約 1 MB）。其授權與開關在設定的進階中。
Timelines: place another timeline of this project on this one as a single clip, at the playhead|Timelines : placez une autre timeline de ce projet sur celle-ci comme un seul clip, à la tête de lecture|Timeline: colloca un'altra timeline di questo progetto su questa come una sola clip, alla testina|タイムライン: このプロジェクトの別のタイムラインを 1 つのクリップとして再生ヘッドの位置に配置|타임라인: 이 프로젝트의 다른 타임라인을 하나의 클립으로 재생 헤드에 배치합니다|Linhas do tempo: coloque outra linha do tempo deste projeto sobre esta como um único clipe, no cursor|Таймлайны: поместите другой таймлайн этого проекта на этот как один клип, у курсора|Zaman çizelgeleri: bu projenin başka bir zaman çizelgesini tek klip olarak oynatma kafasına yerleştirin|时间线：将本项目的另一条时间线作为单个片段放到此时间线的播放头处|時間軸：將本專案的另一條時間軸作為單一片段放到此時間軸的播放頭處
Microphone|Micro|Microfono|マイク|마이크|Microfone|Микрофон|Mikrofon|麦克风|麥克風
Camera|Caméra|Fotocamera|カメラ|카메라|Câmera|Камера|Kamera|摄像头|攝影機
Screen capture|Capture d'écran|Registrazione dello schermo|画面キャプチャ|화면 캡처|Captura de tela|Запись экрана|Ekran kaydı|屏幕录制|螢幕錄製
Could not start the capture|Impossible de démarrer la capture|Impossibile avviare la registrazione|キャプチャを開始できませんでした|캡처를 시작할 수 없습니다|Não foi possível iniciar a captura|Не удалось начать запись|Kayıt başlatılamadı|无法开始录制|無法開始錄製
Transcript: the caption track's text, editable; a time button seeks to its caption|Transcription : le texte de la piste de sous-titres, modifiable ; un bouton d'heure va à son sous-titre|Trascrizione: il testo della traccia dei sottotitoli, modificabile; un pulsante del tempo porta al suo sottotitolo|文字起こし: 字幕トラックのテキストを編集できます。時間ボタンでその字幕へ移動します|대본: 자막 트랙의 텍스트를 편집할 수 있으며, 시간 버튼을 누르면 해당 자막으로 이동합니다|Transcrição: o texto da faixa de legendas, editável; um botão de tempo vai até sua legenda|Расшифровка: текст дорожки субтитров, доступный для правки; кнопка времени переходит к своему субтитру|Deşifre: altyazı parçasının metni, düzenlenebilir; bir zaman düğmesi kendi altyazısına gider|字幕稿：字幕轨道的文本，可编辑；时间按钮跳转到对应字幕|字幕稿：字幕軌道的文字，可編輯；時間按鈕跳轉到對應字幕
Audio stream|Piste audio|Traccia audio|音声ストリーム|오디오 스트림|Faixa de áudio|Аудиодорожка|Ses akışı|音频流|音訊串流
No H.264, HEVC or AV1 encoder works here and OpenH264 is off, so this MP4 export will be saved as WebM. Choose MPEG-4 Part 2 to keep MP4, though Instagram and some players refuse it.|Aucun encodeur H.264, HEVC ou AV1 ne fonctionne ici et OpenH264 est désactivé : cet export MP4 sera enregistré en WebM. Choisissez MPEG-4 Part 2 pour garder le MP4, même si Instagram et certains lecteurs le refusent.|Qui non funziona nessun codificatore H.264, HEVC o AV1 e OpenH264 è disattivato, quindi questa esportazione MP4 verrà salvata come WebM. Scegli MPEG-4 Part 2 per mantenere l'MP4, anche se Instagram e alcuni lettori lo rifiutano.|ここでは H.264、HEVC、AV1 のエンコーダーが使えず OpenH264 もオフのため、この MP4 書き出しは WebM で保存されます。MP4 のままにするには MPEG-4 Part 2 を選んでください（Instagram や一部のプレーヤーは再生できません）。|여기서는 H.264, HEVC, AV1 인코더가 작동하지 않고 OpenH264도 꺼져 있어 이 MP4 내보내기는 WebM으로 저장됩니다. MP4를 유지하려면 MPEG-4 Part 2를 선택하세요. 단, Instagram과 일부 플레이어는 이를 거부합니다.|Nenhum codificador H.264, HEVC ou AV1 funciona aqui e o OpenH264 está desligado, então esta exportação MP4 será salva como WebM. Escolha MPEG-4 Part 2 para manter o MP4, embora o Instagram e alguns players o recusem.|Здесь не работает ни один кодировщик H.264, HEVC или AV1, а OpenH264 выключен, поэтому этот экспорт в MP4 будет сохранён как WebM. Выберите MPEG-4 Part 2, чтобы сохранить MP4, хотя Instagram и некоторые плееры его не принимают.|Burada hiçbir H.264, HEVC veya AV1 kodlayıcı çalışmıyor ve OpenH264 kapalı, bu yüzden bu MP4 dışa aktarımı WebM olarak kaydedilecek. MP4'ü korumak için MPEG-4 Part 2'yi seçin, ancak Instagram ve bazı oynatıcılar bunu reddeder.|此处没有可用的 H.264、HEVC 或 AV1 编码器，且 OpenH264 已关闭，因此这次 MP4 导出将保存为 WebM。若要保留 MP4，请选择 MPEG-4 Part 2，但 Instagram 和部分播放器会拒绝它。|此處沒有可用的 H.264、HEVC 或 AV1 編碼器，且 OpenH264 已關閉，因此這次 MP4 匯出將儲存為 WebM。若要保留 MP4，請選擇 MPEG-4 Part 2，但 Instagram 與部分播放器會拒絕它。
Hip hop|Hip-hop|Hip hop|ヒップホップ|힙합|Hip-hop|Хип-хоп|Hip hop|嘻哈|嘻哈
Electronic|Électronique|Elettronica|エレクトロニック|일렉트로닉|Eletrônica|Электроника|Elektronik|电子|電子
Ambience|Ambiance|Atmosfera|環境音|분위기|Ambiente|Атмосфера|Ortam|环境音|環境音
Short whoosh|Souffle court|Fruscio breve|短いシュッ|짧은 휙|Zunido curto|Короткий свист|Kısa vın|短嗖声|短嗖聲
Long whoosh|Souffle long|Fruscio lungo|長いシュッ|긴 휙|Zunido longo|Долгий свист|Uzun vın|长嗖声|長嗖聲
Sweep up|Balayage montant|Sweep ascendente|上昇スイープ|상승 스윕|Varredura ascendente|Восходящий свип|Yükselen süpürme|上扫|上掃
Reverse cymbal|Cymbale inversée|Piatto al contrario|リバースシンバル|리버스 심벌|Prato reverso|Обратная тарелка|Ters zil|反向镲片|反向鈸
Notification|Notification|Notifica|通知|알림|Notificação|Уведомление|Bildirim|通知|通知
Toggle on|Activer|Attiva|オン|켜기|Ativar|Включение|Aç|开启|開啟
Toggle off|Désactiver|Disattiva|オフ|끄기|Desativar|Выключение|Kapat|关闭|關閉
Key tap|Frappe de touche|Tocco di tasto|キータップ|키 입력|Toque de tecla|Нажатие клавиши|Tuş vuruşu|按键声|按鍵聲
Beep|Bip|Bip|ビープ|삐|Bipe|Писк|Bip|哔声|嗶聲
Level up|Niveau supérieur|Livello superiore|レベルアップ|레벨 업|Subir de nível|Новый уровень|Seviye atlama|升级|升級
Bubble|Bulle|Bolla|泡|거품|Bolha|Пузырь|Baloncuk|气泡|氣泡
Hit|Coup|Colpo|ヒット|타격|Golpe|Удар|Vuruş|击打|擊打
Thud|Bruit sourd|Tonfo|ドスン|쿵|Baque|Глухой удар|Güm|闷响|悶響
Slam|Claquement|Sbattimento|バタン|쾅|Batida|Грохот|Çarpma|猛撞|猛撞
Braam|Braam|Braam|ブラーム|브람|Braam|Браам|Braam|低音轰鸣|低音轟鳴
Sub drop|Chute grave|Caduta sub|サブドロップ|서브 드롭|Queda grave|Саб-дроп|Alt düşüş|低频下坠|低頻下墜
Rumble|Grondement|Rombo|ゴロゴロ|우르릉|Estrondo|Грохотание|Gürleme|隆隆声|隆隆聲
Drum roll|Roulement de tambour|Rullo di tamburi|ドラムロール|드럼 롤|Rufar de tambores|Барабанная дробь|Trampet sesi|鼓声滚奏|鼓聲滾奏
Cymbal crash|Crash de cymbale|Colpo di piatto|シンバルクラッシュ|심벌 크래시|Batida de prato|Удар тарелки|Zil çarpması|镲片撞击|鈸撞擊
Boing|Boing|Boing|ボヨン|보잉|Boing|Буэнг|Boing|啵嘤|啵嚶
Slide whistle up|Sifflet à coulisse montant|Fischietto a coulisse in salita|スライドホイッスル（上）|슬라이드 휘슬 상승|Apito deslizante subindo|Свисток вверх|Kaydırmalı düdük yukarı|滑哨上升|滑哨上升
Slide whistle down|Sifflet à coulisse descendant|Fischietto a coulisse in discesa|スライドホイッスル（下）|슬라이드 휘슬 하강|Apito deslizante descendo|Свисток вниз|Kaydırmalı düdük aşağı|滑哨下降|滑哨下降
Bonk|Bonk|Bonk|ポコッ|콩|Bonk|Бонк|Bonk|咚|咚
Zip|Fermeture éclair|Zip|ジッ|지익|Zíper|Застёжка|Fermuar|拉链声|拉鍊聲
Squeak|Couinement|Squittio|キュッ|찍|Rangido|Писк игрушки|Gıcırtı|吱吱声|吱吱聲
Applause|Applaudissements|Applausi|拍手|박수|Aplausos|Аплодисменты|Alkış|掌声|掌聲
Door knock|Coups à la porte|Bussare alla porta|ノック|노크|Batida na porta|Стук в дверь|Kapı vurma|敲门声|敲門聲
Phone buzz|Vibreur de téléphone|Vibrazione del telefono|スマホのバイブ|휴대폰 진동|Vibração do celular|Вибрация телефона|Telefon titreşimi|手机震动|手機震動
Cash register|Caisse enregistreuse|Registratore di cassa|レジ|금전 등록기|Caixa registradora|Кассовый аппарат|Yazar kasa|收银机|收銀機
Wind|Vent|Vento|風|바람|Vento|Ветер|Rüzgâr|风声|風聲
Waves|Vagues|Onde|波|파도|Ondas|Волны|Dalgalar|海浪|海浪
Crickets|Grillons|Grilli|コオロギ|귀뚜라미|Grilos|Сверчки|Cırcır böcekleri|蟋蟀|蟋蟀
Weather|Météo|Meteo|天気|날씨|Clima|Погода|Hava durumu|天气|天氣
Celebration|Fête|Festa|お祝い|축하|Celebração|Праздник|Kutlama|庆祝|慶祝
Nature|Nature|Natura|自然|자연|Natureza|Природа|Doğa|自然|自然
Food|Nourriture|Cibo|食べ物|음식|Comida|Еда|Yiyecek|食物|食物
Animated titles|Titres animés|Titoli animati|アニメーションタイトル|애니메이션 제목|Títulos animados|Анимированные титры|Animasyonlu başlıklar|动画标题|動畫標題
click one to add it at the playhead, on a new track above everything|cliquez-en un pour l'ajouter à la tête de lecture, sur une nouvelle piste au-dessus de tout|fai clic su uno per aggiungerlo alla testina, su una nuova traccia sopra tutto|クリックすると、再生ヘッドの位置に、すべての上の新しいトラックとして追加されます|클릭하면 재생 헤드 위치의 맨 위 새 트랙에 추가됩니다|clique em um para adicioná-lo no cursor, em uma nova faixa acima de tudo|нажмите, чтобы добавить на новую дорожку поверх всего в позиции курсора|oynatma kafasına, her şeyin üstünde yeni bir parçaya eklemek için birine tıklayın|点击即可在播放头处、于最上层的新轨道添加|點擊即可在播放頭處、於最上層的新軌道加入
Titles|Titres|Titoli|タイトル|제목|Títulos|Титры|Başlıklar|标题|標題
Pop in|Apparition éclair|Comparsa a scatto|ポップイン|팝 인|Surgir|Появление|Belirme|弹入|彈入
Rise up|Montée|Salita|ライズアップ|올라오기|Subir|Подъём|Yükselme|上升|上升
Drop in|Chute|Caduta|ドロップイン|드롭 인|Cair|Падение|Düşme|下落|下落
Subtitle bar|Barre de sous-titre|Barra sottotitoli|字幕バー|자막 바|Barra de legenda|Строка субтитров|Altyazı çubuğu|字幕条|字幕條
Kicker and headline|Surtitre et titre|Occhiello e titolo|見出しとリード|키커와 헤드라인|Chapéu e manchete|Надзаголовок и заголовок|Üst başlık ve manşet|引题与标题|引題與標題
Neon flicker|Néon clignotant|Neon tremolante|ネオンのちらつき|네온 깜빡임|Neon piscando|Мерцающий неон|Titreyen neon|霓虹闪烁|霓虹閃爍
Stamp|Tampon|Timbro|スタンプ|도장|Carimbo|Штамп|Damga|印章|印章
Call to action|Appel à l'action|Invito all'azione|行動喚起|행동 유도|Chamada para ação|Призыв к действию|Harekete geçirici|行动号召|行動呼籲
Quote|Citation|Citazione|引用|인용|Citação|Цитата|Alıntı|引言|引言
Cinematic|Cinématique|Cinematografico|シネマティック|시네마틱|Cinematográfico|Кинематографичный|Sinematik|电影感|電影感
New label|Étiquette nouveau|Etichetta nuovo|NEW ラベル|NEW 라벨|Etiqueta novo|Метка «новое»|Yeni etiketi|“新”标签|「新」標籤
Three words|Trois mots|Tre parole|3 つの言葉|세 단어|Três palavras|Три слова|Üç kelime|三个词|三個詞
Caption box|Encadré de sous-titre|Riquadro didascalia|キャプションボックス|자막 상자|Caixa de legenda|Блок подписи|Altyazı kutusu|字幕框|字幕框
Built in|Intégré|Integrato|組み込み|기본 제공|Incluído|Встроенный|Yerleşik|内置|內建
Cinematic intro|Intro cinématique|Intro cinematografica|シネマティックイントロ|시네마틱 인트로|Intro cinematográfica|Кинематографичное интро|Sinematik giriş|电影感片头|電影感片頭
Lower third|Bandeau|Sottopancia|ローワーサード|하단 자막|Terço inferior|Нижняя плашка|Alt bant|下方字幕条|下方字幕條
Photo slideshow|Diaporama photo|Presentazione di foto|フォトスライドショー|사진 슬라이드쇼|Apresentação de fotos|Фотослайд-шоу|Fotoğraf slayt gösterisi|照片幻灯片|照片投影片
Quote card|Carte citation|Scheda citazione|引用カード|인용 카드|Cartão de citação|Карточка с цитатой|Alıntı kartı|引言卡片|引言卡片
Countdown|Compte à rebours|Conto alla rovescia|カウントダウン|카운트다운|Contagem regressiva|Обратный отсчёт|Geri sayım|倒计时|倒數計時
Split screen|Écran partagé|Schermo diviso|分割画面|분할 화면|Tela dividida|Разделённый экран|Bölünmüş ekran|分屏|分割畫面
Before and after|Avant et après|Prima e dopo|ビフォーアフター|전후 비교|Antes e depois|До и после|Önce ve sonra|前后对比|前後對比
Product showcase|Présentation produit|Vetrina prodotto|商品紹介|제품 소개|Vitrine de produto|Презентация товара|Ürün vitrini|产品展示|產品展示
Vertical short|Vidéo courte verticale|Video breve verticale|縦型ショート|세로형 쇼츠|Vídeo curto vertical|Вертикальное короткое видео|Dikey kısa video|竖屏短视频|直式短影片
Travel opener|Ouverture voyage|Apertura di viaggio|旅行オープニング|여행 오프닝|Abertura de viagem|Заставка путешествия|Seyahat açılışı|旅行开场|旅行開場
Breaking news|Dernière minute|Ultime notizie|速報ニュース|속보|Últimas notícias|Срочные новости|Son dakika|突发新闻|突發新聞
End screen|Écran de fin|Schermata finale|エンドスクリーン|엔드 스크린|Tela final|Финальная заставка|Bitiş ekranı|片尾画面|片尾畫面
Photo 1|Photo 1|Foto 1|写真 1|사진 1|Foto 1|Фото 1|Fotoğraf 1|照片 1|照片 1
Photo 2|Photo 2|Foto 2|写真 2|사진 2|Foto 2|Фото 2|Fotoğraf 2|照片 2|照片 2
Photo 3|Photo 3|Foto 3|写真 3|사진 3|Foto 3|Фото 3|Fotoğraf 3|照片 3|照片 3
Photo 4|Photo 4|Foto 4|写真 4|사진 4|Foto 4|Фото 4|Fotoğraf 4|照片 4|照片 4
Photo 5|Photo 5|Foto 5|写真 5|사진 5|Foto 5|Фото 5|Fotoğraf 5|照片 5|照片 5
Right|Droite|Destra|右|오른쪽|Direita|Справа|Sağ|右|右
Before|Avant|Prima|ビフォー|이전|Antes|До|Önce|之前|之前
After|Après|Dopo|アフター|이후|Depois|После|Sonra|之后|之後
Product photo|Photo du produit|Foto del prodotto|商品写真|제품 사진|Foto do produto|Фото товара|Ürün fotoğrafı|产品照片|產品照片
Clip 1|Clip 1|Clip 1|クリップ 1|클립 1|Clipe 1|Клип 1|Klip 1|片段 1|片段 1
Clip 2|Clip 2|Clip 2|クリップ 2|클립 2|Clipe 2|Клип 2|Klip 2|片段 2|片段 2
Clip 3|Clip 3|Clip 3|クリップ 3|클립 3|Clipe 3|Клип 3|Klip 3|片段 3|片段 3
Next video 1|Vidéo suivante 1|Video successivo 1|次の動画 1|다음 동영상 1|Próximo vídeo 1|Следующее видео 1|Sonraki video 1|下一个视频 1|下一部影片 1
Next video 2|Vidéo suivante 2|Video successivo 2|次の動画 2|다음 동영상 2|Próximo vídeo 2|Следующее видео 2|Sonraki video 2|下一个视频 2|下一部影片 2
Follow size|Suivre la taille|Segui la dimensione|サイズに追従|크기 따라가기|Seguir o tamanho|Следовать за размером|Boyutu takip et|跟随大小|跟隨大小
Follow angle|Suivre l'angle|Segui l'angolo|角度に追従|각도 따라가기|Seguir o ângulo|Следовать за углом|Açıyı takip et|跟随角度|跟隨角度
H.264 without a hardware encoder|H.264 sans encodeur matériel|H.264 senza codificatore hardware|ハードウェアエンコーダーなしの H.264|하드웨어 인코더 없는 H.264|H.264 sem codificador por hardware|H.264 без аппаратного кодировщика|Donanım kodlayıcısı olmadan H.264|无硬件编码器时的 H.264|無硬體編碼器時的 H.264
For computers that cannot encode H.264 themselves.|Pour les ordinateurs qui ne savent pas encoder le H.264 eux-mêmes.|Per i computer che non sanno codificare H.264 da soli.|H.264 を自前でエンコードできないコンピューター向け。|H.264를 스스로 인코딩할 수 없는 컴퓨터용입니다.|Para computadores que não conseguem codificar H.264 sozinhos.|Для компьютеров, которые не умеют кодировать H.264 сами.|H.264'ü kendisi kodlayamayan bilgisayarlar için.|适用于自身无法编码 H.264 的电脑。|適用於本身無法編碼 H.264 的電腦。
Use OpenH264 when this computer has no H.264 encoder|Utiliser OpenH264 quand cet ordinateur n'a pas d'encodeur H.264|Usa OpenH264 quando questo computer non ha un codificatore H.264|このコンピューターに H.264 エンコーダーがないとき OpenH264 を使う|이 컴퓨터에 H.264 인코더가 없으면 OpenH264 사용|Usar o OpenH264 quando este computador não tiver codificador H.264|Использовать OpenH264, если на этом компьютере нет кодировщика H.264|Bu bilgisayarda H.264 kodlayıcı yoksa OpenH264 kullan|此电脑没有 H.264 编码器时使用 OpenH264|此電腦沒有 H.264 編碼器時使用 OpenH264
This computer encodes H.264 itself, so OpenH264 is not used.|Cet ordinateur encode lui-même le H.264, OpenH264 n'est donc pas utilisé.|Questo computer codifica H.264 da solo, quindi OpenH264 non viene usato.|このコンピューターは H.264 を自前でエンコードできるため、OpenH264 は使いません。|이 컴퓨터는 H.264를 직접 인코딩하므로 OpenH264를 사용하지 않습니다.|Este computador codifica H.264 sozinho, então o OpenH264 não é usado.|Этот компьютер сам кодирует H.264, поэтому OpenH264 не используется.|Bu bilgisayar H.264'ü kendisi kodluyor, bu yüzden OpenH264 kullanılmıyor.|此电脑可自行编码 H.264，因此不使用 OpenH264。|此電腦可自行編碼 H.264，因此不使用 OpenH264。
Downloads from Cisco, about 1 MB, the first time an H.264 export needs it.|Se télécharge depuis Cisco (environ 1 Mo) la première fois qu'un export H.264 en a besoin.|Si scarica da Cisco (circa 1 MB) la prima volta che un'esportazione H.264 ne ha bisogno.|H.264 の書き出しで初めて必要になったときに Cisco からダウンロードします（約 1 MB）。|H.264 내보내기에 처음 필요할 때 Cisco에서 내려받습니다(약 1MB).|É baixado da Cisco (cerca de 1 MB) na primeira vez que uma exportação H.264 precisar dele.|Загружается с сайта Cisco (около 1 МБ), когда экспорту в H.264 он впервые понадобится.|Bir H.264 dışa aktarımı ilk kez ihtiyaç duyduğunda Cisco'dan indirilir (yaklaşık 1 MB).|首次有 H.264 导出需要时从 Cisco 下载（约 1 MB）。|首次有 H.264 匯出需要時從 Cisco 下載（約 1 MB）。
Downloaded from Cisco (version {version}).|Téléchargé depuis Cisco (version {version}).|Scaricato da Cisco (versione {version}).|Cisco からダウンロード済み（バージョン {version}）。|Cisco에서 내려받음(버전 {version}).|Baixado da Cisco (versão {version}).|Загружено с сайта Cisco (версия {version}).|Cisco'dan indirildi (sürüm {version}).|已从 Cisco 下载（版本 {version}）。|已從 Cisco 下載（版本 {version}）。
Off: MP4 exports on this computer are saved as WebM.|Désactivé : les exports MP4 sont enregistrés en WebM sur cet ordinateur.|Disattivato: le esportazioni MP4 vengono salvate come WebM su questo computer.|オフ: このコンピューターでは MP4 の書き出しが WebM で保存されます。|꺼짐: 이 컴퓨터에서는 MP4 내보내기가 WebM으로 저장됩니다.|Desligado: as exportações MP4 são salvas como WebM neste computador.|Выключено: на этом компьютере экспорт в MP4 сохраняется как WebM.|Kapalı: Bu bilgisayarda MP4 dışa aktarımları WebM olarak kaydedilir.|已关闭：此电脑上的 MP4 导出将保存为 WebM。|已關閉：此電腦上的 MP4 匯出將儲存為 WebM。
Cisco publishes no OpenH264 library for this computer, so MP4 exports are saved as WebM.|Cisco ne publie pas de bibliothèque OpenH264 pour cet ordinateur : les exports MP4 sont enregistrés en WebM.|Cisco non pubblica una libreria OpenH264 per questo computer, quindi le esportazioni MP4 vengono salvate come WebM.|Cisco はこのコンピューター向けの OpenH264 ライブラリを提供していないため、MP4 の書き出しは WebM で保存されます。|Cisco가 이 컴퓨터용 OpenH264 라이브러리를 제공하지 않으므로 MP4 내보내기는 WebM으로 저장됩니다.|A Cisco não publica uma biblioteca OpenH264 para este computador, então as exportações MP4 são salvas como WebM.|Cisco не выпускает библиотеку OpenH264 для этого компьютера, поэтому экспорт в MP4 сохраняется как WebM.|Cisco bu bilgisayar için OpenH264 kitaplığı yayımlamıyor, bu yüzden MP4 dışa aktarımları WebM olarak kaydedilir.|Cisco 未提供适用于此电脑的 OpenH264 库，因此 MP4 导出将保存为 WebM。|Cisco 未提供適用於此電腦的 OpenH264 程式庫，因此 MP4 匯出將儲存為 WebM。
Cisco's H.264 patent licence covers personal use and uses that earn no money. For anything else, get your own licence or export WebM.|La licence de brevets H.264 de Cisco couvre l'usage personnel et les usages qui ne rapportent pas d'argent. Pour le reste, obtenez votre propre licence ou exportez en WebM.|La licenza dei brevetti H.264 di Cisco copre l'uso personale e gli usi che non generano guadagni. Per il resto, procurati una licenza tua o esporta in WebM.|Cisco の H.264 特許ライセンスが対象とするのは個人的な利用と収益を生まない利用です。それ以外は独自にライセンスを取得するか、WebM で書き出してください。|Cisco의 H.264 특허 라이선스는 개인적 사용과 수익이 없는 사용에만 적용됩니다. 그 밖의 경우에는 별도 라이선스를 받거나 WebM으로 내보내세요.|A licença de patentes H.264 da Cisco cobre o uso pessoal e usos que não geram receita. Para o resto, obtenha sua própria licença ou exporte em WebM.|Патентная лицензия Cisco на H.264 распространяется на личное использование и использование без дохода. В остальных случаях получите собственную лицензию или экспортируйте в WebM.|Cisco'nun H.264 patent lisansı kişisel kullanımı ve gelir getirmeyen kullanımları kapsar. Diğer durumlar için kendi lisansınızı alın veya WebM olarak dışa aktarın.|Cisco 的 H.264 专利许可涵盖个人使用及不产生收入的使用。其他用途请自行取得许可，或导出为 WebM。|Cisco 的 H.264 專利授權涵蓋個人使用及不產生收入的使用。其他用途請自行取得授權，或匯出為 WebM。
Licence|Licence|Licenza|ライセンス|라이선스|Licença|Лицензия|Lisans|许可|授權
Saved as WebM: this computer has no H.264 encoder, and OpenH264 is off or could not be downloaded.|Enregistré en WebM : cet ordinateur n'a pas d'encodeur H.264, et OpenH264 est désactivé ou n'a pas pu être téléchargé.|Salvato come WebM: questo computer non ha un codificatore H.264 e OpenH264 è disattivato o non è stato possibile scaricarlo.|WebM で保存しました。このコンピューターには H.264 エンコーダーがなく、OpenH264 はオフか、ダウンロードできませんでした。|WebM으로 저장했습니다. 이 컴퓨터에는 H.264 인코더가 없고, OpenH264가 꺼져 있거나 내려받지 못했습니다.|Salvo como WebM: este computador não tem codificador H.264, e o OpenH264 está desligado ou não pôde ser baixado.|Сохранено как WebM: на этом компьютере нет кодировщика H.264, а OpenH264 выключен или не загрузился.|WebM olarak kaydedildi: Bu bilgisayarda H.264 kodlayıcı yok ve OpenH264 kapalı ya da indirilemedi.|已保存为 WebM：此电脑没有 H.264 编码器，且 OpenH264 已关闭或无法下载。|已儲存為 WebM：此電腦沒有 H.264 編碼器，且 OpenH264 已關閉或無法下載。
AI agents|Agents IA|Agenti IA|AI エージェント|AI 에이전트|Agentes de IA|ИИ-агенты|Yapay zekâ ajanları|AI 智能体|AI 代理
Let Claude Code, Codex, Cursor or any MCP client drive formcut. Add it once; while formcut is running, the agent finds it by itself.|Laissez Claude Code, Codex, Cursor ou tout client MCP piloter formcut. Ajoutez-le une fois ; tant que formcut tourne, l'agent le trouve tout seul.|Lascia che Claude Code, Codex, Cursor o qualsiasi client MCP controllino formcut. Aggiungilo una volta; finché formcut è aperto, l'agente lo trova da solo.|Claude Code、Codex、Cursor などの MCP クライアントから formcut を操作できます。一度追加すれば、formcut の起動中はエージェントが自動で見つけます。|Claude Code, Codex, Cursor 등 MCP 클라이언트가 formcut을 조작하게 하세요. 한 번 추가하면 formcut이 실행 중일 때 에이전트가 알아서 찾습니다.|Deixe o Claude Code, o Codex, o Cursor ou qualquer cliente MCP controlar o formcut. Adicione uma vez; enquanto o formcut estiver aberto, o agente o encontra sozinho.|Позвольте Claude Code, Codex, Cursor или любому MCP-клиенту управлять formcut. Добавьте один раз; пока formcut запущен, агент найдёт его сам.|Claude Code, Codex, Cursor veya herhangi bir MCP istemcisinin formcut'ı yönetmesine izin verin. Bir kez ekleyin; formcut açıkken ajan onu kendisi bulur.|让 Claude Code、Codex、Cursor 或任何 MCP 客户端操控 formcut。只需添加一次；formcut 运行时，智能体会自动找到它。|讓 Claude Code、Codex、Cursor 或任何 MCP 用戶端操控 formcut。只需加入一次；formcut 執行時，代理會自動找到它。
Run this in a terminal:|Exécutez ceci dans un terminal :|Esegui questo in un terminale:|ターミナルで実行:|터미널에서 실행:|Execute isto em um terminal:|Выполните в терминале:|Bunu bir terminalde çalıştırın:|在终端中运行：|在終端機中執行：
Add this to {file}:|Ajoutez ceci à {file} :|Aggiungi questo a {file}:|{file} に追加:|{file}에 추가:|Adicione isto a {file}:|Добавьте в {file}:|Bunu {file} dosyasına ekleyin:|添加到 {file}：|加入到 {file}：
Any other MCP client: the command and its arguments|Tout autre client MCP : la commande et ses arguments|Qualsiasi altro client MCP: il comando e i suoi argomenti|その他の MCP クライアント: コマンドと引数|기타 MCP 클라이언트: 명령과 인수|Qualquer outro cliente MCP: o comando e seus argumentos|Любой другой MCP-клиент: команда и её аргументы|Diğer MCP istemcileri: komut ve argümanları|其他 MCP 客户端：命令及其参数|其他 MCP 用戶端：指令及其參數
Copied|Copié|Copiato|コピーしました|복사됨|Copiado|Скопировано|Kopyalandı|已复制|已複製
Triangle|Triangle|Triangolo|三角形|삼각형|Triângulo|Треугольник|Üçgen|三角形|三角形
Pentagon|Pentagone|Pentagono|五角形|오각형|Pentágono|Пятиугольник|Beşgen|五边形|五邊形
Hexagon|Hexagone|Esagono|六角形|육각형|Hexágono|Шестиугольник|Altıgen|六边形|六邊形
Octagon|Octogone|Ottagono|八角形|팔각형|Octógono|Восьмиугольник|Sekizgen|八边形|八邊形
Star|Étoile|Stella|星形|별|Estrela|Звезда|Yıldız|星形|星形
Six-point star|Étoile à six branches|Stella a sei punte|六芒星|육각별|Estrela de seis pontas|Шестиконечная звезда|Altı köşeli yıldız|六角星|六角星
Heart|Cœur|Cuore|ハート|하트|Coração|Сердце|Kalp|心形|心形
Cross|Croix|Croce|十字|십자|Cruz|Крест|Artı|十字形|十字形
Arrow|Flèche|Freccia|矢印|화살표|Seta|Стрелка|Ok|箭头|箭頭
Chevron|Chevron|Chevron|シェブロン|갈매기표|Chevron|Шеврон|Köşeli ok|V 形|V 形
Trapezoid|Trapèze|Trapezio|台形|사다리꼴|Trapézio|Трапеция|Yamuk|梯形|梯形
Linear|Linéaire|Lineare|リニア|선형|Linear|Линейная|Doğrusal|线性|線性
Person|Personne|Persona|人物|인물|Pessoa|Человек|Kişi|人物|人物
Object|Objet|Oggetto|オブジェクト|사물|Objeto|Объект|Nesne|物体|物件
Soft edge|Bord doux|Bordo morbido|柔らかい縁|부드러운 가장자리|Borda suave|Мягкий край|Yumuşak kenar|柔和边缘|柔和邊緣
Hard edge|Bord net|Bordo netto|くっきりした縁|선명한 가장자리|Borda dura|Жёсткий край|Sert kenar|硬边缘|硬邊緣
Tight|Serré|Stretto|タイト|타이트|Justo|Плотно|Sıkı|紧贴|緊貼
Loose|Large|Largo|ゆったり|여유 있게|Folgado|Свободно|Gevşek|宽松|寬鬆
Hair detail|Détail des cheveux|Dettaglio capelli|髪の細部|머리카락 세부|Detalhe do cabelo|Детали волос|Saç ayrıntısı|发丝细节|髮絲細節
Fine detail|Détail fin|Dettaglio fine|細部|세밀한 부분|Detalhe fino|Мелкие детали|İnce ayrıntı|精细细节|精細細節
Green screen|Écran vert|Green screen|グリーンバック|그린 스크린|Tela verde|Зелёный фон|Yeşil perde|绿幕|綠幕
Blue screen|Écran bleu|Blue screen|ブルーバック|블루 스크린|Tela azul|Синий фон|Mavi perde|蓝幕|藍幕
Import package|Importer un paquet|Importa pacchetto|パッケージを読み込む|패키지 가져오기|Importar pacote|Импортировать пакет|Paketi içe aktar|导入效果包|匯入效果包
Remove package|Supprimer le paquet|Rimuovi pacchetto|パッケージを削除|패키지 제거|Remover pacote|Удалить пакет|Paketi kaldır|移除效果包|移除效果包
Could not import the package: {reason}|Impossible d'importer le paquet : {reason}|Impossibile importare il pacchetto: {reason}|パッケージを読み込めませんでした: {reason}|패키지를 가져올 수 없습니다: {reason}|Não foi possível importar o pacote: {reason}|Не удалось импортировать пакет: {reason}|Paket içe aktarılamadı: {reason}|无法导入效果包:{reason}|無法匯入效果包:{reason}
Imported {name}|{name} importé|{name} importato|{name} を読み込みました|{name}을(를) 가져왔습니다|{name} importado|{name} импортирован|{name} içe aktarıldı|已导入 {name}|已匯入 {name}
Package removed|Paquet supprimé|Pacchetto rimosso|パッケージを削除しました|패키지를 제거했습니다|Pacote removido|Пакет удалён|Paket kaldırıldı|已移除效果包|已移除效果包
A clip in this project uses this package. Remove it from that clip first.|Un clip de ce projet utilise ce paquet. Retirez-le d'abord de ce clip.|Una clip di questo progetto usa questo pacchetto. Rimuovilo prima da quella clip.|このプロジェクトのクリップがこのパッケージを使っています。先にそのクリップから外してください。|이 프로젝트의 클립이 이 패키지를 사용합니다. 먼저 그 클립에서 제거하세요.|Um clipe deste projeto usa este pacote. Remova-o desse clipe primeiro.|Этот пакет используется клипом в проекте. Сначала уберите его из клипа.|Bu projedeki bir klip bu paketi kullanıyor. Önce o klipten kaldırın.|本项目中有片段使用此效果包。请先从该片段中移除。|本專案中有片段使用此效果包。請先從該片段中移除。
Remove this package? You can import it again later.|Supprimer ce paquet ? Vous pourrez l'importer de nouveau plus tard.|Rimuovere questo pacchetto? Potrai importarlo di nuovo in seguito.|このパッケージを削除しますか?あとで再び読み込めます。|이 패키지를 제거할까요? 나중에 다시 가져올 수 있습니다.|Remover este pacote? Você poderá importá-lo novamente depois.|Удалить этот пакет? Позже его можно импортировать снова.|Bu paket kaldırılsın mı? Daha sonra yeniden içe aktarabilirsiniz.|移除此效果包?以后可以再次导入。|移除此效果包?之後可以再次匯入。
Your own effect packages appear here. Choose Import package to add a .zip of a package folder, or its manifest.json.|Vos propres paquets d'effets apparaissent ici. Choisissez Importer un paquet pour ajouter le .zip d'un dossier de paquet ou son manifest.json.|I tuoi pacchetti di effetti compaiono qui. Scegli Importa pacchetto per aggiungere lo .zip di una cartella di pacchetto o il suo manifest.json.|自分のエフェクトパッケージはここに表示されます。「パッケージを読み込む」で、パッケージフォルダの .zip またはその manifest.json を追加できます。|직접 만든 효과 패키지가 여기에 표시됩니다. 패키지 가져오기를 눌러 패키지 폴더의 .zip이나 manifest.json을 추가하세요.|Seus próprios pacotes de efeitos aparecem aqui. Escolha Importar pacote para adicionar o .zip de uma pasta de pacote ou o manifest.json dela.|Здесь появляются ваши пакеты эффектов. Нажмите «Импортировать пакет», чтобы добавить .zip папки пакета или его manifest.json.|Kendi efekt paketleriniz burada görünür. Bir paket klasörünün .zip dosyasını veya manifest.json dosyasını eklemek için Paketi içe aktar'ı seçin.|你自己的效果包会显示在这里。选择“导入效果包”,添加包文件夹的 .zip 或其 manifest.json。|你自己的效果包會顯示在這裡。選擇「匯入效果包」,加入套件資料夾的 .zip 或其 manifest.json。
No effects match your search.|Aucun effet ne correspond à votre recherche.|Nessun effetto corrisponde alla ricerca.|検索に一致するエフェクトはありません。|검색과 일치하는 효과가 없습니다.|Nenhum efeito corresponde à sua pesquisa.|Нет эффектов, подходящих под запрос.|Aramanızla eşleşen efekt yok.|没有与搜索匹配的效果。|沒有與搜尋相符的效果。
Nothing here yet.|Rien ici pour l'instant.|Ancora niente qui.|まだ何もありません。|아직 아무것도 없습니다.|Nada aqui ainda.|Здесь пока ничего нет.|Burada henüz bir şey yok.|这里还没有内容。|這裡還沒有內容。
Intensity|Intensité|Intensità|強さ|강도|Intensidade|Интенсивность|Yoğunluk|强度|強度
Segments|Segments|Segmenti|セグメント|분할 수|Segmentos|Сегменты|Bölümler|分段|分段
Spacing|Espacement|Spaziatura|間隔|간격|Espaçamento|Интервал|Aralık|间距|間距
Twist|Torsion|Torsione|ねじれ|비틀림|Torção|Закручивание|Bükülme|扭曲|扭曲
Tiles|Tuiles|Tessere|タイル|타일|Blocos|Плитки|Döşemeler|平铺数|平鋪數
Density|Densité|Densità|密度|밀도|Densidade|Плотность|Yoğunluk derecesi|密度|密度
Curvature|Courbure|Curvatura|湾曲|곡률|Curvatura|Кривизна|Eğrilik|曲率|曲率
Horizontal position|Position horizontale|Posizione orizzontale|水平位置|가로 위치|Posição horizontal|Положение по горизонтали|Yatay konum|水平位置|水平位置
Vertical position|Position verticale|Posizione verticale|垂直位置|세로 위치|Posição vertical|Положение по вертикали|Dikey konum|垂直位置|垂直位置
Pixel size|Taille des pixels|Dimensione pixel|ピクセルサイズ|픽셀 크기|Tamanho do pixel|Размер пикселя|Piksel boyutu|像素大小|像素大小
Cell size|Taille des cellules|Dimensione cella|セルサイズ|셀 크기|Tamanho da célula|Размер ячейки|Hücre boyutu|单元大小|單元大小
LED size|Taille des LED|Dimensione LED|LEDサイズ|LED 크기|Tamanho do LED|Размер светодиода|LED boyutu|LED 大小|LED 大小
Dot size|Taille des points|Dimensione punti|ドットサイズ|점 크기|Tamanho do ponto|Размер точки|Nokta boyutu|网点大小|網點大小
Line detail|Détail des lignes|Dettaglio linee|線の細かさ|선 세부|Detalhe da linha|Детализация линий|Çizgi ayrıntısı|线条细节|線條細節
Noise|Bruit|Rumore|ノイズ|노이즈|Ruído|Шум|Gürültü|噪点|雜訊
Engine|Moteur|Motore|エンジン|엔진|Mecanismo|Движок|Motor|引擎|引擎
Install|Installer|Installa|インストール|설치|Instalar|Установить|Yükle|安装|安裝
Clone a voice from|Cloner une voix depuis|Clona una voce da|声をクローンする元|음성 복제 원본|Clonar uma voz de|Клонировать голос из|Sesi şuradan klonla|克隆声音来源|複製聲音來源
I have the speaker's permission|J'ai l'autorisation de la personne qui parle|Ho il permesso di chi parla|話者の許可を得ています|화자의 허락을 받았습니다|Tenho a permissão de quem fala|У меня есть разрешение говорящего|Konuşan kişinin iznini aldım|我已获得说话人的许可|我已取得說話者的許可
Expression|Expression|Espressività|表現|표현|Expressão|Выразительность|İfade|表现力|表現力
Kokoro, Apache-2.0: many voices and languages, fast.|Kokoro, Apache-2.0 : de nombreuses voix et langues, rapide.|Kokoro, Apache-2.0: molte voci e lingue, veloce.|Kokoro(Apache-2.0):多くの声と言語、高速。|Kokoro, Apache-2.0: 다양한 목소리와 언어, 빠름.|Kokoro, Apache-2.0: muitas vozes e idiomas, rápido.|Kokoro, Apache-2.0: много голосов и языков, быстро.|Kokoro, Apache-2.0: birçok ses ve dil, hızlı.|Kokoro,Apache-2.0:声音和语言众多,速度快。|Kokoro,Apache-2.0:聲音和語言眾多,速度快。
Pocket TTS by Kyutai, CC-BY-4.0: small and quick on a CPU; built-in voices, or clone one with permission.|Pocket TTS de Kyutai, CC-BY-4.0 : léger et rapide sur CPU ; voix intégrées, ou clonez-en une avec autorisation.|Pocket TTS di Kyutai, CC-BY-4.0: piccolo e veloce su CPU; voci incluse, o clonane una con il permesso.|Kyutai の Pocket TTS(CC-BY-4.0):CPU で小さく高速。内蔵の声、または許可を得て声をクローン。|Kyutai의 Pocket TTS, CC-BY-4.0: CPU에서 작고 빠름. 내장 목소리를 쓰거나 허락을 받아 복제.|Pocket TTS da Kyutai, CC-BY-4.0: pequeno e rápido na CPU; vozes incluídas ou clone uma com permissão.|Pocket TTS от Kyutai, CC-BY-4.0: компактный и быстрый на CPU; встроенные голоса или клон с разрешения.|Kyutai'nin Pocket TTS'i, CC-BY-4.0: CPU'da küçük ve hızlı; yerleşik sesler ya da izinle bir ses klonu.|Kyutai 的 Pocket TTS,CC-BY-4.0:在 CPU 上小巧快速;内置声音,或经许可克隆声音。|Kyutai 的 Pocket TTS,CC-BY-4.0:在 CPU 上小巧快速;內建聲音,或經許可複製聲音。
Chatterbox by Resemble AI, MIT: expressive, multilingual, clones a voice from seconds of audio. Its audio carries an inaudible watermark.|Chatterbox de Resemble AI, MIT : expressif, multilingue, clone une voix à partir de quelques secondes d'audio. Son audio porte un filigrane inaudible.|Chatterbox di Resemble AI, MIT: espressivo, multilingue, clona una voce da pochi secondi di audio. Il suo audio contiene una filigrana impercettibile.|Resemble AI の Chatterbox(MIT):表現力豊かで多言語、数秒の音声から声をクローン。出力には聞こえない透かしが入ります。|Resemble AI의 Chatterbox, MIT: 표현력 있고 다국어를 지원하며 몇 초의 음성으로 목소리를 복제. 출력에는 들리지 않는 워터마크가 들어갑니다.|Chatterbox da Resemble AI, MIT: expressivo, multilíngue, clona uma voz com segundos de áudio. Seu áudio leva uma marca d'água inaudível.|Chatterbox от Resemble AI, MIT: выразительный, многоязычный, клонирует голос по нескольким секундам аудио. Его звук несёт неслышимый водяной знак.|Resemble AI'nin Chatterbox'ı, MIT: etkileyici, çok dilli, birkaç saniyelik sesten klonlar. Çıktısı duyulmayan bir filigran taşır.|Resemble AI 的 Chatterbox,MIT:富有表现力,支持多语言,几秒音频即可克隆声音。其音频带有听不见的水印。|Resemble AI 的 Chatterbox,MIT:富有表現力,支援多語言,幾秒音訊即可複製聲音。其音訊帶有聽不見的浮水印。
Install this engine to use it; it downloads PyTorch and its model once.|Installez ce moteur pour l'utiliser ; il télécharge PyTorch et son modèle une seule fois.|Installa questo motore per usarlo; scarica PyTorch e il suo modello una sola volta.|使うにはこのエンジンをインストールしてください。PyTorch とモデルを一度だけダウンロードします。|사용하려면 이 엔진을 설치하세요. PyTorch와 모델을 한 번만 내려받습니다.|Instale este mecanismo para usá-lo; ele baixa o PyTorch e seu modelo uma única vez.|Установите этот движок, чтобы использовать его; он один раз загрузит PyTorch и свою модель.|Kullanmak için bu motoru yükleyin; PyTorch'u ve modelini bir kez indirir.|安装此引擎即可使用;它只需下载一次 PyTorch 和模型。|安裝此引擎即可使用;它只需下載一次 PyTorch 和模型。
Installing; this can take several minutes.|Installation en cours ; cela peut prendre plusieurs minutes.|Installazione in corso; può richiedere alcuni minuti.|インストール中です。数分かかることがあります。|설치 중입니다. 몇 분 걸릴 수 있습니다.|Instalando; isso pode levar alguns minutos.|Идёт установка; это может занять несколько минут.|Yükleniyor; bu birkaç dakika sürebilir.|正在安装,可能需要几分钟。|正在安裝,可能需要幾分鐘。
Color|Couleur|Colore|カラー|색상|Cor|Цвет|Renk|调色|調色
Select a video or image clip to grade it.|Sélectionnez un clip vidéo ou image pour l'étalonner.|Seleziona una clip video o immagine per correggerne il colore.|グレーディングするビデオまたは画像クリップを選択してください。|색 보정할 비디오나 이미지 클립을 선택하세요.|Selecione um clipe de vídeo ou imagem para fazer a correção de cor.|Выберите видео- или графический клип для цветокоррекции.|Renk düzenlemek için bir video veya görsel klibi seçin.|选择一个视频或图像片段进行调色。|選擇一個影片或圖像片段進行調色。
Scopes|Moniteurs|Scope|スコープ|스코프|Scopes|Мониторы|Ölçekler|示波器|示波器
Waveform|Forme d'onde|Forma d'onda|波形|파형|Forma de onda|Осциллограф|Dalga formu|波形图|波形圖
RGB parade|Parade RVB|Parata RGB|RGBパレード|RGB 퍼레이드|Parada RGB|RGB-парад|RGB geçit|RGB 分量图|RGB 分量圖
Vectorscope|Vectorscope|Vettorscopio|ベクトルスコープ|벡터스코프|Vectorscópio|Вектороскоп|Vektörskop|矢量示波器|向量示波器
Histogram|Histogramme|Istogramma|ヒストグラム|히스토그램|Histograma|Гистограмма|Histogram|直方图|直方圖
Wheels|Roues|Ruote|ホイール|휠|Rodas|Круги|Tekerlekler|色轮|色輪
Drag to balance the colour; double-click to reset|Faites glisser pour équilibrer la couleur ; double-cliquez pour réinitialiser|Trascina per bilanciare il colore; doppio clic per ripristinare|ドラッグで色のバランスを調整、ダブルクリックでリセット|드래그해 색 균형을 조정하고, 더블클릭하면 초기화합니다|Arraste para equilibrar a cor; clique duas vezes para redefinir|Перетащите, чтобы сбалансировать цвет; двойной щелчок сбрасывает|Rengi dengelemek için sürükleyin; sıfırlamak için çift tıklayın|拖动以调整色彩平衡；双击重置|拖曳以調整色彩平衡；按兩下重設
Gain|Gain|Guadagno|ゲイン|게인|Ganho|Усиление|Kazanç|增益|增益
Offset|Offset|Offset|オフセット|오프셋|Deslocamento|Смещение|Kaydırma|偏移|偏移
Primaries|Primaires|Primarie|プライマリー|프라이머리|Primárias|Первичная коррекция|Birincil|一级调色|一級調色
Pivot|Pivot|Pivot|ピボット|피벗|Pivô|Опорная точка|Pivot|轴心|軸心
Color boost|Renfort des couleurs|Potenziamento colore|カラーブースト|색상 부스트|Reforço de cor|Усиление цвета|Renk güçlendirme|色彩增强|色彩增強
Hue|Teinte|Tonalità|色相|색조|Matiz|Оттенок|Ton|色相|色相
Curves|Courbes|Curve|カーブ|커브|Curvas|Кривые|Eğriler|曲线|曲線
Luma|Luma|Luma|輝度|루마|Luma|Яркость|Luma|亮度|亮度
Red|Rouge|Rosso|赤|빨강|Vermelho|Красный|Kırmızı|红|紅
Green|Vert|Verde|緑|초록|Verde|Зелёный|Yeşil|绿|綠
Blue|Bleu|Blu|青|파랑|Azul|Синий|Mavi|蓝|藍
Hue vs hue|Teinte/teinte|Tonalità vs tonalità|色相対色相|색조 대 색조|Matiz vs. matiz|Оттенок/оттенок|Ton/ton|色相对色相|色相對色相
Hue vs sat|Teinte/saturation|Tonalità vs sat.|色相対彩度|색조 대 채도|Matiz vs. sat.|Оттенок/насыщенность|Ton/doygunluk|色相对饱和度|色相對飽和度
Lum vs sat|Luminance/saturation|Luminanza vs sat.|輝度対彩度|휘도 대 채도|Lum. vs. sat.|Яркость/насыщенность|Parlaklık/doygunluk|亮度对饱和度|亮度對飽和度
Click to add a point, drag to move it, double-click to remove it.|Cliquez pour ajouter un point, faites-le glisser pour le déplacer, double-cliquez pour le supprimer.|Fai clic per aggiungere un punto, trascinalo per spostarlo, doppio clic per rimuoverlo.|クリックで点を追加、ドラッグで移動、ダブルクリックで削除します。|클릭해 점을 추가하고, 드래그해 옮기고, 더블클릭해 지웁니다.|Clique para adicionar um ponto, arraste para movê-lo e clique duas vezes para removê-lo.|Щелчок добавляет точку, перетаскивание перемещает, двойной щелчок удаляет.|Nokta eklemek için tıklayın, taşımak için sürükleyin, kaldırmak için çift tıklayın.|单击添加点，拖动移动，双击删除。|按一下新增點，拖曳移動，按兩下刪除。
Highlights|Hautes lumières|Luci|ハイライト|하이라이트|Realces|Света|Parlak alanlar|高光|亮部
Shadows|Ombres|Ombre|シャドウ|그림자|Sombras|Тени|Gölgeler|阴影|陰影
Whites|Blancs|Bianchi|白レベル|흰색 계열|Brancos|Белые|Beyazlar|白色|白色
Blacks|Noirs|Neri|黒レベル|검은색 계열|Pretos|Чёрные|Siyahlar|黑色|黑色
Brightness|Luminosité|Luminosità|明るさ|밝기|Brilho|Яркость|Parlaklık|亮度|亮度
Reset grade|Réinitialiser l'étalonnage|Ripristina correzione|グレードをリセット|색 보정 초기화|Redefinir correção|Сбросить цветокоррекцию|Renk düzenlemeyi sıfırla|重置调色|重設調色
Copy grade|Copier l'étalonnage|Copia correzione|グレードをコピー|색 보정 복사|Copiar correção|Копировать цветокоррекцию|Renk düzenlemeyi kopyala|复制调色|複製調色
Paste grade|Coller l'étalonnage|Incolla correzione|グレードを貼り付け|색 보정 붙여넣기|Colar correção|Вставить цветокоррекцию|Renk düzenlemeyi yapıştır|粘贴调色|貼上調色
Looks|Looks|Look|ルック|룩|Visuais|Образы|Görünümler|风格|風格
Packages|Paquets|Pacchetti|パッケージ|패키지|Pacotes|Пакеты|Paketler|效果包|效果包
Oil Paint|Peinture à l'huile|Pittura a olio|油絵|유화|Pintura a óleo|Масляная живопись|Yağlı boya|油画|油畫
Hex Pixelate|Pixellisation hexagonale|Pixel esagonali|六角形モザイク|육각형 픽셀|Pixelado hexagonal|Шестиугольные пиксели|Altıgen piksel|六边形像素化|六邊形像素化
Neon Edges|Contours néon|Bordi al neon|ネオンエッジ|네온 윤곽선|Bordas neon|Неоновые контуры|Neon kenarlar|霓虹边缘|霓虹邊緣
Pop Art Grid|Grille pop art|Griglia pop art|ポップアートグリッド|팝아트 그리드|Grade pop art|Сетка поп-арт|Pop art ızgarası|波普艺术网格|普普藝術網格
Stained Glass|Vitrail|Vetrata|ステンドグラス|스테인드글라스|Vitral|Витраж|Vitray|彩色玻璃|彩繪玻璃
Infrared|Infrarouge|Infrarosso|赤外線|적외선|Infravermelho|Инфракрасный|Kızılötesi|红外|紅外線
Clarity|Clarté|Chiarezza|明瞭度|선명도|Clareza|Чёткость|Netlik|清晰度|清晰度
Dehaze|Correction du voile|Rimozione foschia|かすみの除去|안개 제거|Remover névoa|Устранение дымки|Pus giderme|去雾|去霧
Skin Smoothing|Lissage de la peau|Levigatura della pelle|美肌|피부 보정|Suavização de pele|Сглаживание кожи|Cilt yumuşatma|磨皮|磨皮
Block Glitch|Glitch en blocs|Glitch a blocchi|ブロックグリッチ|블록 글리치|Glitch em blocos|Блочный глитч|Blok bozulması|块状故障|區塊故障
Anaglyph 3D|Anaglyphe 3D|Anaglifo 3D|アナグリフ3D|애너글리프 3D|Anáglifo 3D|Анаглиф 3D|Anaglif 3D|红蓝 3D|紅藍 3D
LED Wall|Mur LED|Parete LED|LEDウォール|LED 월|Painel de LED|LED-экран|LED duvar|LED 屏幕墙|LED 螢幕牆
Retro Dither|Tramage rétro|Retinatura retrò|レトロディザ|레트로 디더|Pontilhado retrô|Ретро-дизеринг|Retro benekleme|复古抖动|復古抖動
Fog|Brouillard|Nebbia|霧|안개|Neblina|Туман|Sis|雾|霧
Sparkles|Scintillements|Scintille|きらめき|반짝임|Brilhos|Искры|Pırıltılar|闪光|閃光
VHS Tape|Cassette VHS|Nastro VHS|VHSテープ|VHS 테이프|Fita VHS|Кассета VHS|VHS kaset|VHS 录像带|VHS 錄影帶
CRT Screen|Écran cathodique|Schermo CRT|ブラウン管|CRT 화면|Tela CRT|ЭЛТ-экран|CRT ekran|CRT 屏幕|CRT 螢幕
Lens Flare|Reflet d'objectif|Riflesso dell'obiettivo|レンズフレア|렌즈 플레어|Reflexo de lente|Блик объектива|Lens parlaması|镜头光晕|鏡頭光暈
Push Down|Pousser vers le bas|Spingi giù|下へプッシュ|아래로 밀기|Empurrar para baixo|Сдвиг вниз|Aşağı it|向下推|向下推
Cover Left|Recouvrir vers la gauche|Copri a sinistra|左へカバー|왼쪽으로 덮기|Cobrir para a esquerda|Наезд влево|Sola örtme|向左覆盖|向左覆蓋
Cover Up|Recouvrir vers le haut|Copri verso l'alto|上へカバー|위로 덮기|Cobrir para cima|Наезд вверх|Yukarı örtme|向上覆盖|向上覆蓋
Clock Wipe|Balayage horaire|Tendina a orologio|時計ワイプ|시계 방향 와이프|Transição de relógio|Часовая шторка|Saat silme|时钟擦除|時鐘擦除
Blinds|Stores|Veneziane|ブラインド|블라인드|Persianas|Жалюзи|Jaluzi|百叶窗|百葉窗
Diagonal Wipe|Balayage diagonal|Tendina diagonale|斜めワイプ|대각선 와이프|Transição diagonal|Диагональная шторка|Çapraz silme|对角擦除|對角擦除
Pixel Dissolve|Fondu pixelisé|Dissolvenza a pixel|ピクセルディゾルブ|픽셀 디졸브|Dissolução em pixels|Пиксельное растворение|Piksel geçişi|像素溶解|像素溶解
Blur Fade|Fondu flou|Dissolvenza sfocata|ぼかしフェード|블러 페이드|Esmaecer com desfoque|Размытое затухание|Bulanık geçiş|模糊淡化|模糊淡化
Spin|Rotation|Rotazione|スピン|회전|Giro|Вращение|Döndürme|旋转|旋轉
Diamond|Losange|Rombo|ダイヤモンド|다이아몬드|Losango|Ромб|Elmas|菱形|菱形
Barn Door|Porte de grange|Apertura a porta|観音開き|양문 열기|Porta de celeiro|Распашные двери|Ahır kapısı|对开门|對開門
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
Medium (in the engine)|Medium (dans le moteur)|Medium (nel motore)|Medium（エンジン内）|Medium(엔진에서)|Medium (no motor)|Medium (в движке)|Medium (motorda)|Medium（在引擎中）|Medium（在引擎中）
Large (in the engine, most accurate)|Large (dans le moteur, le plus précis)|Large (nel motore, il più preciso)|Large（エンジン内、最も正確）|Large(엔진에서, 가장 정확)|Large (no motor, mais preciso)|Large (в движке, самая точная)|Large (motorda, en doğru)|Large（在引擎中，最准确）|Large（在引擎中，最準確）
Engine, {model}: {percent}%|Moteur, {model} : {percent}%|Motore, {model}: {percent}%|エンジン、{model}：{percent}%|엔진, {model}: {percent}%|Motor, {model}: {percent}%|Движок, {model}: {percent}%|Motor, {model}: {percent}%|引擎，{model}：{percent}%|引擎，{model}：{percent}%
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
Codec|Codec|Codec|コーデック|코덱|Codec|Кодек|Kodek|编解码器|編解碼器
Size|Taille|Dimensione|サイズ|크기|Tamanho|Размер|Boyut|尺寸|尺寸
Timeline|Montage|Timeline|タイムライン|타임라인|Linha do tempo|Таймлайн|Zaman çizelgesi|时间线|時間軸
10-bit colour|Couleur 10 bits|Colore a 10 bit|10ビットカラー|10비트 색상|Cor de 10 bits|10-битный цвет|10 bit renk|10 位色彩|10 位色彩
Exact preview colours (slower)|Couleurs exactes de l’aperçu (plus lent)|Colori esatti dell’anteprima (più lento)|プレビューと同じ色（低速）|미리보기와 동일한 색상(느림)|Cores exatas da pré-visualização (mais lento)|Точные цвета предпросмотра (медленнее)|Önizlemeyle birebir renkler (daha yavaş)|与预览完全一致的颜色（较慢）|與預覽完全一致的色彩（較慢）
Estimated size|Taille estimée|Dimensione stimata|推定サイズ|예상 크기|Tamanho estimado|Примерный размер|Tahmini boyut|预计大小|預計大小
Inspector|Inspecteur|Ispettore|インスペクター|인스펙터|Inspetor|Инспектор|Denetçi|检查器|檢視器
left|gauche|sinistra|左|왼쪽|esquerda|слева|sol|左侧|左側
right|droite|destra|右|오른쪽|direita|справа|sağ|右侧|右側
bottom|bas|in basso|下|아래|abaixo|снизу|alt|底部|底部
Style removed|Style retiré|Stile rimosso|スタイルを解除しました|스타일을 제거했습니다|Estilo removido|Стиль снят|Stil kaldırıldı|已移除样式|已移除樣式
Not available in this layout|Indisponible dans cette disposition|Non disponibile in questo layout|このレイアウトでは利用できません|이 레이아웃에서는 사용할 수 없습니다|Indisponível neste layout|Недоступно в этом макете|Bu düzende kullanılamaz|此布局中不可用|此配置中不可用
Cut this sentence and the footage under it|Couper cette phrase et les images en dessous|Taglia questa frase e il girato sotto di essa|この文とその下の映像をカット|이 문장과 그 아래 영상을 잘라내기|Cortar esta frase e a filmagem sob ela|Вырезать это предложение и кадры под ним|Bu cümleyi ve altındaki görüntüyü kes|剪掉这句话及其下方的素材|剪掉這句話及其下方的素材
Emphasis|Accent|Enfasi|強調|강조|Ênfase|Акцент|Vurgu|强调|強調
Words to colour, separated by commas|Mots à colorer, séparés par des virgules|Parole da colorare, separate da virgole|色を付ける単語（カンマ区切り）|색을 입힐 단어(쉼표로 구분)|Palavras a colorir, separadas por vírgulas|Слова для окраски, через запятую|Renklendirilecek kelimeler, virgülle ayrılmış|要上色的词，用逗号分隔|要上色的詞，用逗號分隔
Emphasis colour|Couleur de l'accent|Colore dell'enfasi|強調の色|강조 색|Cor da ênfase|Цвет акцента|Vurgu rengi|强调颜色|強調顏色
Colour these words|Colorer ces mots|Colora queste parole|これらの単語に色を付ける|이 단어에 색 입히기|Colorir estas palavras|Окрасить эти слова|Bu kelimeleri renklendir|为这些词上色|為這些詞上色
Clear emphasis|Retirer l'accent|Rimuovi l'enfasi|強調を解除|강조 지우기|Remover a ênfase|Убрать акцент|Vurguyu kaldır|清除强调|清除強調
Caption looks: one tap styles the track's captions and the next transcription|Styles de sous-titres : un appui habille les sous-titres de la piste et la prochaine transcription|Stili dei sottotitoli: un tocco veste i sottotitoli della traccia e la prossima trascrizione|字幕のルック：1 回のタップでトラックの字幕と次の文字起こしにスタイルを適用|자막 스타일: 한 번의 탭으로 트랙의 자막과 다음 전사에 스타일 적용|Estilos de legenda: um toque estiliza as legendas da faixa e a próxima transcrição|Стили субтитров: одно нажатие оформляет субтитры дорожки и следующую расшифровку|Altyazı görünümleri: bir dokunuş, parçanın altyazılarını ve sonraki dökümü biçimlendirir|字幕样式：轻点一次即可为轨道字幕和下一次转录设置样式|字幕樣式：輕點一次即可為軌道字幕和下一次轉錄設定樣式
Caption look applied|Style de sous-titres appliqué|Stile dei sottotitoli applicato|字幕のルックを適用しました|자막 스타일을 적용했습니다|Estilo de legenda aplicado|Стиль субтитров применён|Altyazı görünümü uygulandı|已应用字幕样式|已套用字幕樣式
Export as .fc (the project with its media)|Exporter en .fc (le projet avec ses médias)|Esporta come .fc (il progetto con i suoi media)|.fc として書き出す（メディアを含むプロジェクト）|.fc로 내보내기(미디어를 포함한 프로젝트)|Exportar como .fc (o projeto com a sua mídia)|Экспортировать как .fc (проект с его медиа)|.fc olarak dışa aktar (medyasıyla birlikte proje)|导出为 .fc（含媒体的项目）|匯出為 .fc（含媒體的專案）
Writing the .fc package|Écriture du paquet .fc|Scrittura del pacchetto .fc|.fc パッケージを書き込み中|.fc 패키지 작성 중|A escrever o pacote .fc|Запись пакета .fc|.fc paketi yazılıyor|正在写入 .fc 包|正在寫入 .fc 套件
Importing the project package|Importation du paquet de projet|Importazione del pacchetto del progetto|プロジェクトパッケージを読み込み中|프로젝트 패키지 가져오는 중|A importar o pacote do projeto|Импорт пакета проекта|Proje paketi içe aktarılıyor|正在导入项目包|正在匯入專案套件
Projects imported|Projets importés|Progetti importati|プロジェクトを読み込みました|프로젝트를 가져왔습니다|Projetos importados|Проекты импортированы|Projeler içe aktarıldı|已导入项目|已匯入專案
Community packages|Paquets de la communauté|Pacchetti della community|コミュニティパッケージ|커뮤니티 패키지|Pacotes da comunidade|Пакеты сообщества|Topluluk paketleri|社区包|社群套件
Reading the package registry|Lecture du registre des paquets|Lettura del registro dei pacchetti|パッケージレジストリを読み込み中|패키지 레지스트리 읽는 중|A ler o registo de pacotes|Чтение реестра пакетов|Paket kaydı okunuyor|正在读取包注册表|正在讀取套件註冊表
Could not read the registry: {reason}|Impossible de lire le registre : {reason}|Impossibile leggere il registro: {reason}|レジストリを読み込めませんでした：{reason}|레지스트리를 읽을 수 없습니다: {reason}|Não foi possível ler o registo: {reason}|Не удалось прочитать реестр: {reason}|Kayıt okunamadı: {reason}|无法读取注册表：{reason}|無法讀取註冊表：{reason}
Install|Installer|Installa|インストール|설치|Instalar|Установить|Yükle|安装|安裝
Downloading and checking {name}|Téléchargement et vérification de {name}|Download e verifica di {name}|{name} をダウンロードして確認中|{name} 다운로드 및 확인 중|A transferir e verificar {name}|Загрузка и проверка {name}|{name} indiriliyor ve denetleniyor|正在下载并检查 {name}|正在下載並檢查 {name}
Sounds and music|Sons et musique|Suoni e musica|効果音と音楽|효과음과 음악|Sons e música|Звуки и музыка|Sesler ve müzik|音效与音乐|音效與音樂
Search Openverse|Rechercher sur Openverse|Cerca su Openverse|Openverse を検索|Openverse 검색|Pesquisar no Openverse|Поиск в Openverse|Openverse'te ara|搜索 Openverse|搜尋 Openverse
Openverse results|Résultats Openverse|Risultati Openverse|Openverse の結果|Openverse 결과|Resultados do Openverse|Результаты Openverse|Openverse sonuçları|Openverse 结果|Openverse 結果
Open the source page|Ouvrir la page source|Apri la pagina di origine|元のページを開く|원본 페이지 열기|Abrir a página de origem|Открыть страницу источника|Kaynak sayfayı aç|打开来源页面|開啟來源頁面
Openly licensed sounds, music and images; each carries its own licence and creator|Sons, musiques et images sous licence libre ; chacun porte sa licence et son auteur|Suoni, musica e immagini con licenza aperta; ognuno porta la propria licenza e il proprio autore|オープンライセンスの効果音・音楽・画像。それぞれにライセンスと作者が付いています|공개 라이선스 효과음, 음악, 이미지. 각 항목에 라이선스와 제작자가 함께합니다|Sons, música e imagens com licença aberta; cada um traz a sua licença e o seu autor|Звуки, музыка и изображения с открытой лицензией; у каждого своя лицензия и автор|Açık lisanslı sesler, müzik ve görseller; her biri kendi lisansını ve yaratıcısını taşır|开放许可的音效、音乐和图片；每一项都附带各自的许可和作者|開放授權的音效、音樂和圖片；每一項都附帶各自的授權和作者
Angle|Caméra|Camera|カメラ|카메라|Câmera|Камера|Kamera|机位|機位
Multicam|Multicaméra|Multicamera|マルチカム|멀티캠|Multicâmera|Мультикамера|Çoklu kamera|多机位|多機位
Sound from|Son de|Audio da|音声|소리|Som de|Звук из|Ses kaynağı|声音来自|聲音來自
the angle shown|la caméra affichée|la camera mostrata|表示中のカメラ|표시된 카메라|a câmera exibida|показанной камеры|gösterilen kamera|当前机位|目前機位
Multicam: a chip or a number key cuts at the playhead and switches the tail; at a clip's edge it switches the whole clip|Multicaméra : une puce ou une touche chiffrée coupe à la tête de lecture et bascule la suite ; au bord d'un clip, tout le clip bascule|Multicamera: un chip o un tasto numerico taglia sulla testina e cambia il resto; al bordo di una clip cambia l'intera clip|マルチカム：チップまたは数字キーで再生ヘッド位置でカットして以降を切り替え。クリップの端では全体を切り替え|멀티캠: 칩이나 숫자 키가 재생 헤드에서 자르고 뒷부분을 전환합니다. 클립 가장자리에서는 클립 전체를 전환합니다|Multicâmera: um chip ou uma tecla numérica corta no cursor e troca o restante; na borda de um clipe troca o clipe inteiro|Мультикамера: кнопка или цифровая клавиша режет на курсоре и переключает остаток; на краю клипа переключается весь клип|Çoklu kamera: bir düğme veya sayı tuşu oynatma kafasında keser ve devamını değiştirir; klip kenarında tüm klip değişir|多机位：点击机位或按数字键在播放头处切开并切换后半段；在片段边缘则切换整个片段|多機位：點擊機位或按數字鍵在播放頭處切開並切換後半段；在片段邊緣則切換整個片段`;
export const PHRASES: Record<string, Record<string, string>> = Object.fromEntries(codes.map(c => [c, {}]));
for (const row of rows.split("\n")) {
  const [source, ...values] = row.split("|");
  if (values.length !== codes.length) throw new Error(`Invalid language row: ${source}`);
  codes.forEach((code, i) => PHRASES[code][source] = values[i]);
}
export function languagePack(english: Record<string, string>): Record<string, Record<string, string>> {
  return Object.fromEntries(codes.map(code => [code, Object.fromEntries(Object.entries(english).map(([key, value]) => [key, PHRASES[code][value] ?? value]))]));
}
