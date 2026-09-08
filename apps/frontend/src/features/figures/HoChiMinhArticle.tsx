/**
 * Bài về Hồ Chí Minh — chuyển thẳng từ docs/design/mockups/nhan-vat-ho-chi-minh.html.
 *
 * Nội dung biên soạn tay từ nguồn ngoài (Bảo tàng Hồ Chí Minh, Hồ Chí Minh toàn tập),
 * KHÔNG lấy từ kho tri thức: kho chỉ có văn SGK cắt theo đoạn, ghép lại không thành một
 * bài đọc được. Ảnh nằm ở public/danh-nhan/ho-chi-minh/ (tải sẵn từ Wikimedia Commons)
 * thay vì hotlink, để trang không phụ thuộc mạng ngoài lúc demo.
 *
 * Class trong file này do features/figures/figure-page.css định nghĩa, không phải Tailwind.
 */

const IMG = "/danh-nhan/ho-chi-minh";

export function HoChiMinhArticle() {
  return (
    <>
      <header className="hero">
        <div className="hero-grid">
          <div>
            <span className="eyebrow">Nhân vật lịch sử</span>
            <h1>Hồ Chí Minh</h1>
            <div className="lifespan">1890 — 1969</div>
            <div className="aliases">
              <span className="alias">Nguyễn Sinh Cung</span>
              <span className="alias">Nguyễn Tất Thành</span>
              <span className="alias">Văn Ba</span>
              <span className="alias">Nguyễn Ái Quốc</span>
              <span className="alias">Thầu Chín</span>
              <span className="alias">Tống Văn Sơ</span>
              <span className="alias now">Hồ Chí Minh</span>
            </div>
            <figure className="hero-quote">
              <p>
                “Dân ta phải biết sử ta,
                <br />
                Cho tường gốc tích nước nhà Việt Nam.”
              </p>
              <cite>
                Mở đầu <em>Lịch sử nước ta</em> — Việt Minh Tuyên truyền Bộ xuất bản, tháng 2-1942
              </cite>
            </figure>
          </div>
          <figure className="portrait">
            <img src={`${IMG}/chan-dung-1946.jpg`} alt="Chân dung Chủ tịch Hồ Chí Minh, khoảng 1946–1947" />
            <figcaption>
              Chân dung Chủ tịch Hồ Chí Minh, khoảng 1946–1947. Ảnh khuyết danh — phạm vi công cộng,
              Wikimedia Commons.
            </figcaption>
          </figure>
        </div>
        <div className="scrollhint">Cuộn để xem</div>
      </header>

      <section id="cuocdoi">
        <div className="wrap">
          <div className="sec-head rv">
            <span className="sec-num">01</span>
            <h2>Cuộc đời và sự nghiệp</h2>
            <p className="note">
              Bảy mươi chín năm, từ ngôi nhà tranh làng Hoàng Trù đến Quảng trường Ba Đình — và ba
              mươi năm ở giữa dành cho việc đi tìm một con đường.
            </p>
          </div>

          <div className="article">
            <div className="facts wide rv">
              <h3>Tóm lược</h3>
              <dl>
                <div>
                  <dt>Tên khai sinh</dt>
                  <dd>Nguyễn Sinh Cung</dd>
                </div>
                <div>
                  <dt>Sinh</dt>
                  <dd>19-5-1890 · làng Hoàng Trù, xã Kim Liên, Nam Đàn, Nghệ An</dd>
                </div>
                <div>
                  <dt>Mất</dt>
                  <dd>2-9-1969 · Hà Nội, thọ 79 tuổi</dd>
                </div>
                <div>
                  <dt>Song thân</dt>
                  <dd>Nguyễn Sinh Sắc (1862–1929) · Hoàng Thị Loan (1868–1901)</dd>
                </div>
                <div>
                  <dt>Cương vị</dt>
                  <dd>
                    Chủ tịch nước Việt Nam Dân chủ Cộng hòa (1945–1969) · Thủ tướng (1945–1955) ·
                    Chủ tịch Đảng (1951–1969)
                  </dd>
                </div>
                <div>
                  <dt>Tên gọi, bí danh</dt>
                  <dd>
                    Văn Ba · Nguyễn Ái Quốc · Thầu Chín · Tống Văn Sơ · Hồ Chí Minh, cùng hàng trăm
                    bút danh khác
                  </dd>
                </div>
              </dl>
            </div>

            <div className="ch rv">
              <span className="yrs">1890 — 1910</span>
              <h3>Con nhà nho xứ Nghệ</h3>
            </div>
            <div className="chunk rv">
              <p className="lead">
                Ngày <strong>19-5-1890</strong>, tại làng Hoàng Trù — quê ngoại — thuộc xã Kim Liên,
                huyện Nam Đàn, tỉnh Nghệ An, Bác ra đời và được đặt tên là{" "}
                <strong>Nguyễn Sinh Cung</strong>. Cha là ông Nguyễn Sinh Sắc (1862–1929), mồ côi từ
                nhỏ, được một nhà nho trong làng nuôi cho ăn học rồi đỗ Phó bảng. Mẹ là bà Hoàng Thị
                Loan (1868–1901), người con gái làng Hoàng Trù dệt vải nuôi chồng đi thi. Trên Bác còn một chị và một anh — bà Nguyễn Thị Thanh và ông Nguyễn Sinh Khiêm — cả hai về sau
                đều bị thực dân Pháp bắt giam vì hoạt động yêu nước.
              </p>
              <p>
                Năm 1895, cả nhà theo cha vào Huế. Sáu năm sau, sau khi sinh người con út, bà Hoàng
                Thị Loan mất ở tuổi ba mươi ba giữa kinh thành, lúc chồng đang đi thi xa; Bác khi ấy mười một tuổi, bồng em đi xin sữa khắp xóm. Cũng năm ấy, khi cha đỗ Phó bảng, Bác được đặt tên mới theo lệ: <strong>Nguyễn Tất Thành</strong>.
              </p>
              <p>
                Bác lớn lên giữa hai luồng ảnh hưởng. Trong nhà là chữ Hán, là những câu chuyện về
                Phan Đình Phùng, về các sĩ phu Cần Vương mà bạn bè của cha vẫn bàn bên chén nước.
                Ngoài cổng Trường Tiểu học Pháp – Việt Đông Ba rồi Trường Quốc học Huế là tiếng Pháp
                và ba chữ <em>Tự do – Bình đẳng – Bác ái</em> — ba chữ mà về sau Bác kể lại rằng mình muốn sang tận nơi xem người ta hiểu chúng ra sao. Tháng 4-1908, Bác làm phiên dịch cho
                nông dân Thừa Thiên trong cuộc biểu tình chống sưu thuế, bị nhà trường ghi vào sổ đen
                và phải rời Huế.
              </p>
              <p>
                Bác đi dần vào Nam: dừng ở Quy Nhơn học thêm tiếng Pháp, rồi đến Phan Thiết. Trong
                khoảng 1910–1911, tại Trường Dục Thanh — ngôi trường do các sĩ phu phong trào Duy Tân
                lập ra — thầy giáo trẻ Nguyễn Tất Thành dạy chữ Quốc ngữ và thể dục. Đầu năm 1911, Bác
                vào Sài Gòn.
              </p>
              <figure className="fig land">
                <img src={`${IMG}/truong-duc-thanh.jpg`} alt="Trường Dục Thanh ở Phan Thiết" loading="lazy" />
                <figcaption>
                  <span className="yr">Trường Dục Thanh, Phan Thiết</span>Ngôi trường của các sĩ phu
                  Duy Tân, nơi thầy giáo Nguyễn Tất Thành dừng chân dạy học trước khi vào Sài Gòn. Nay
                  là di tích trong khu lưu niệm bên sông Cà Ty.
                  <span className="cr">
                    Ảnh: Bùi Thụy Đào Nguyên · CC BY-SA 3.0 —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:Tr%C6%B0%E1%BB%9Dng_D%E1%BB%A5c_Thanh.jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
            </div>

            <div className="ch rv">
              <span className="yrs">1911 — 1917</span>
              <h3>Ra đi, và sáu năm làm thuê</h3>
            </div>
            <div className="chunk rv">
              <figure className="fig right land">
                <img
                  src={`${IMG}/bien-carlton-london.jpg`}
                  alt="Tấm biển kỷ niệm nơi từng là khách sạn Carlton ở London"
                  loading="lazy"
                />
                <figcaption>
                  <span className="yr">Haymarket, London</span>Tấm biển do Hội Anh – Việt gắn tại nơi
                  từng là khách sạn Carlton, ghi rằng người phụ bếp năm 1913 ở đây về sau lập ra nước
                  Việt Nam hiện đại.
                  <span className="cr">
                    Ảnh: Spudgun67 · CC BY-SA 4.0 —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:Ho_Chi_Minh_1890-1969_founder_of_modern_Vietnam_worked_in_1913_at_the_Carlton_Hotel_which_stood_on_this_site.jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
              <p>
                Ngày <strong>5-6-1911</strong>, từ bến Nhà Rồng, Bác — khi ấy hai mươi mốt tuổi —
                lấy tên <strong>Văn Ba</strong> xuống tàu buôn <em>Amiral Latouche-Tréville</em> làm
                phụ bếp. Lớp cha anh đi trước — Phan Bội Châu, Phan Châu Trinh — hướng về Nhật Bản, về
                Trung Hoa; Bác chọn hướng ngược lại: sang chính nước Pháp, sang phương Tây, để xem cái
                gì nằm sau những khẩu hiệu ấy.
              </p>
              <p>
                Sáu năm tiếp theo là sáu năm lao động chân tay. Phụ bếp trên tàu qua các cảng châu
                Phi. Làm vườn, đốt lò, làm bánh, quét tuyết ở Mỹ rồi ở Anh. Ở New York, Bác nhìn tượng
                Nữ thần Tự do và ghi lại rằng dưới chân bức tượng ấy người da đen vẫn bị hành hình; ở
                London, Bác phụ bếp trong khách sạn Carlton và tối đến đi học tiếng Anh. Chuyến đi dài
                dạy Bác một điều sách vở không dạy: ở đâu người lao động cũng bị bóc lột như nhau, và
                vì thế ở đâu cũng có bạn.
              </p>
            </div>

            <div className="ch rv">
              <span className="yrs">1917 — 1923</span>
              <h3>Nguyễn Ái Quốc ở Paris</h3>
            </div>
            <div className="chunk rv">
              <figure className="fig left doc">
                <img
                  src={`${IMG}/yeu-sach-1919.jpg`}
                  alt="Bản Yêu sách của nhân dân An Nam, tiếng Pháp, năm 1919"
                  loading="lazy"
                />
                <figcaption>
                  <span className="yr">18-6-1919</span>
                  <em>Revendications du Peuple Annamite</em> — bản Yêu sách tám điểm gửi Hội nghị
                  Versailles, ký tên Nguyễn Ái Quốc.
                  <span className="cr">
                    Tư liệu · CC BY 4.0 —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:Revendications_du_Peuple_Annamite.jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
              <p>
                Cuối năm 1917 Bác từ Anh trở lại Pháp, sống ở Paris, được Phan Châu Trinh và luật sư
                Phan Văn Trường giúp đỡ nơi ở và việc làm — nghề rửa ảnh, vẽ đồ mỹ nghệ “kiểu Trung
                Hoa”. Năm 1919 Bác gia nhập Đảng Xã hội Pháp, tổ chức duy nhất ở Pháp khi ấy lên tiếng
                bênh vực các dân tộc thuộc địa.
              </p>
              <p>
                Ngày <strong>18-6-1919</strong>, khi các nước thắng trận họp ở Versailles để chia lại
                thế giới, bản <strong>Yêu sách của nhân dân An Nam</strong> gồm tám điểm được gửi tới
                hội nghị, ký một cái tên chưa ai từng nghe: <strong>Nguyễn Ái Quốc</strong>. Bản yêu
                sách không đòi độc lập ngay — nó đòi ân xá tù chính trị, tự do báo chí và lập hội, tự
                do đi lại, quyền học hành, và thay chế độ sắc lệnh bằng chế độ pháp luật. Hội nghị
                không trả lời. Nhưng từ đó, cái tên ấy trở thành một cái tên.
              </p>
              <p>
                Tháng 7-1920, trên báo <em>Nhân đạo</em> (L’Humanité), Bác đọc{" "}
                <em>
                  Sơ thảo lần thứ nhất những luận cương về vấn đề dân tộc và vấn đề thuộc địa
                </em>{" "}
                của Lênin. Bốn mươi năm sau, Bác kể lại giây phút ấy:
              </p>
              <figure className="pull">
                <blockquote>
                  Luận cương của Lênin làm cho tôi rất cảm động, phấn khởi, sáng tỏ, tin tưởng biết
                  bao! Tôi vui mừng đến phát khóc lên. Ngồi một mình trong buồng mà tôi nói to lên như
                  đang nói trước quần chúng đông đảo: Hỡi đồng bào bị đọa đày đau khổ! Đây là cái cần
                  thiết cho chúng ta, đây là con đường giải phóng chúng ta!
                </blockquote>
                <cite>
                  <em>Con đường dẫn tôi đến chủ nghĩa Lênin</em>, viết năm 1960
                </cite>
              </figure>
              <p>
                Cuối tháng 12-1920, tại Đại hội lần thứ 18 của Đảng Xã hội Pháp họp ở thành phố Tours,
                Bác bỏ phiếu tán thành gia nhập Quốc tế thứ ba và trở thành một trong những người sáng
                lập Đảng Cộng sản Pháp — người cộng sản Việt Nam đầu tiên. Những năm sau đó ở Paris là
                những năm vừa viết vừa tổ chức: cùng những người yêu nước Bắc Phi, Mađagaxca, Angti
                lập <strong>Hội Liên hiệp thuộc địa</strong> (1921); ra báo <em>Le Paria</em> — Người
                cùng khổ — số đầu ngày 1-4-1922, tự viết bài, tự vẽ tranh châm biếm, tự đem báo đi
                bán; và hoàn thành <em>Bản án chế độ thực dân Pháp</em>, in tại Paris năm 1925.
              </p>
            </div>

            <div className="row c4 wide rv">
              <figure className="fig">
                <img
                  src={`${IMG}/marseille-1921.jpg`}
                  alt="Nguyễn Ái Quốc, đại biểu Đông Dương tại Đại hội Đảng Cộng sản Pháp ở Marseille, tháng 12-1921"
                  loading="lazy"
                />
                <figcaption>
                  <span className="yr">26-12-1921</span>Đại biểu Đông Dương tại Đại hội Đảng Cộng sản
                  Pháp ở Marseille — bức ảnh báo chí đầu tiên chụp Bác.
                  <span className="cr">
                    Ảnh: Agence Meurisse / BNF Gallica · phạm vi công cộng —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:Nguyen_A%C3%AFn_Nu%C3%A4%27C_(Ho-Chi-Minh),_d%C3%A9l%C3%A9gu%C3%A9_indochinois,_Congr%C3%A8s_communiste_de_Marseille,_1921,_Meurisse,_BNF_Gallica.jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
              <figure className="fig">
                <img src={`${IMG}/chan-dung-1922.jpg`} alt="Chân dung Nguyễn Ái Quốc năm 1922" loading="lazy" />
                <figcaption>
                  <span className="yr">1922</span>Chân dung những năm làm báo <em>Le Paria</em> trong
                  căn phòng thuê ở ngõ Compoint, Paris.
                  <span className="cr">
                    Ảnh khuyết danh · phạm vi công cộng —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:Portrait_dated_1922_of_Ho_Chi_Minh.jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
              <figure className="fig doc">
                <img
                  src={`${IMG}/tranh-le-paria-1924.jpg`}
                  alt="Tranh châm biếm của Nguyễn Ái Quốc đăng trên báo Le Paria"
                  loading="lazy"
                />
                <figcaption>
                  <span className="yr">1924</span>Tranh châm biếm do chính Nguyễn Ái Quốc vẽ cho{" "}
                  <em>Le Paria</em>, về cảnh sưu thuế ở thuộc địa.
                  <span className="cr">
                    Tranh: Nguyễn Ái Quốc · phạm vi công cộng —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:AnhNAQ1.jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
              <figure className="fig doc">
                <img
                  src={`${IMG}/ban-an-che-do-thuc-dan-phap.jpg`}
                  alt="Bìa sách Le Procès de la Colonisation Française — Bản án chế độ thực dân Pháp"
                  loading="lazy"
                />
                <figcaption>
                  <span className="yr">1925</span>
                  <em>Le Procès de la Colonisation Française</em> — Bản án chế độ thực dân Pháp, in ở
                  Paris rồi bí mật chuyển về nước.
                  <span className="cr">
                    Tư liệu · phạm vi công cộng —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:Le_Proc%C3%A8s_de_la_Colonisation_Fran%C3%A7aise.jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
            </div>

            <div className="ch rv">
              <span className="yrs">1923 — 1929</span>
              <h3>Mátxcơva, Quảng Châu, Xiêm</h3>
            </div>
            <div className="chunk rv">
              <figure className="fig right">
                <img src={`${IMG}/chan-dung-1924.jpg`} alt="Chân dung Nguyễn Ái Quốc năm 1924" loading="lazy" />
                <figcaption>
                  <span className="yr">1924</span>Năm Bác đọc tham luận về vấn đề thuộc địa ở
                  Mátxcơva, rồi lên đường sang Quảng Châu.
                  <span className="cr">
                    Ảnh khuyết danh · phạm vi công cộng —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:Nguyen_Ai_Quoc_in_1924.jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
              <p>
                Tháng 6-1923, Bác bí mật rời Paris sang Mátxcơva. Ở Liên Xô, Bác dự Hội nghị Quốc tế
                Nông dân, làm việc tại Quốc tế Cộng sản, và tại Đại hội lần thứ V (tháng 6 và 7-1924)
                trình bày một luận điểm mà phong trào cộng sản châu Âu khi ấy ít nghe: thuộc địa không
                phải là chuyện phụ — “nọc độc và sức sống” của chủ nghĩa tư bản đang nằm ở đó, và cách
                mạng thuộc địa có thể nổ ra trước, rồi giúp lại cách mạng chính quốc.
              </p>
              <p>
                Ngày <strong>11-11-1924</strong> Bác tới Quảng Châu, nơi thanh niên Việt Nam yêu nước
                đang tụ về. Từ nhóm Tâm Tâm xã, Bác lập nhóm Cộng sản đoàn (2-1925), rồi tháng 6-1925
                lập <strong>Hội Việt Nam Cách mạng Thanh niên</strong>. Tuần báo <em>Thanh niên</em> ra
                số đầu ngày 21-6-1925.
              </p>
              <figure className="fig left doc">
                <img src={`${IMG}/duong-kach-menh-1927.jpg`} alt="Bìa cuốn Đường Kách mệnh, 1927" loading="lazy" />
                <figcaption>
                  <span className="yr">1927</span>
                  <em>Đường Kách mệnh</em> — tập bài giảng ở Quảng Châu, in bằng bản in đá và chuyển bí
                  mật về trong nước.
                  <span className="cr">
                    Tư liệu · phạm vi công cộng —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:Duong_Kach_Menh.pdf"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
              <p>
                Bác trực tiếp mở các lớp huấn luyện chính trị cho thanh niên bí mật từ trong nước
                sang; khoảng bảy mươi lăm người qua ba khóa, học xong phần lớn trở về “vô sản hóa”
                trong hầm mỏ, nhà máy, đồn điền. Bài giảng của những lớp ấy được in thành{" "}
                <em>Đường Kách mệnh</em> — cuốn sách gối đầu giường của cả một thế hệ.
              </p>
              <p>
                Sau chính biến tháng 4-1927 ở Trung Quốc, Bác phải rời Quảng Châu. Năm 1928 Bác sang
                Xiêm, sống trong các làng Việt kiều ở Uđon, Phichit, Noỏng Khai với cái tên{" "}
                <strong>Thầu Chín</strong>: dạy học, ra báo <em>Thân ái</em>, đào giếng, trồng cây,
                gánh nước như một người dân thường — và lặng lẽ gây dựng cơ sở.
              </p>
            </div>

            <div className="ch rv">
              <span className="yrs">1930 — 1940</span>
              <h3>Thành lập Đảng, và mười năm lưu lạc</h3>
            </div>
            <div className="chunk rv">
              <p>
                Cuối năm 1929, phong trào trong nước đã đủ lớn nhưng lại chia thành ba tổ chức cộng
                sản công kích lẫn nhau. Được Quốc tế Cộng sản ủy nhiệm, Nguyễn Ái Quốc từ Xiêm sang
                Hương Cảng, triệu tập và chủ trì hội nghị hợp nhất họp bí mật đầu năm 1930 tại Cửu
                Long. Hội nghị nhất trí hợp nhất thành <strong>Đảng Cộng sản Việt Nam</strong> và
                thông qua Chính cương vắn tắt, Sách lược vắn tắt do chính Bác khởi thảo; ngày{" "}
                <strong>3-2-1930</strong> về sau được lấy làm ngày thành lập Đảng.
              </p>
              <figure className="fig right">
                <img
                  src={`${IMG}/tong-van-so-1931.jpg`}
                  alt="Tống Văn Sơ, tức Nguyễn Ái Quốc, khi bị bắt ở Hồng Kông tháng 6-1931"
                  loading="lazy"
                />
                <figcaption>
                  <span className="yr">Tháng 6-1931</span>Ảnh trong hồ sơ cảnh sát Hồng Kông, lập dưới
                  cái tên Tống Văn Sơ — người mà nhà cầm quyền Pháp đang truy tìm để dẫn độ.
                  <span className="cr">
                    Ảnh khuyết danh · phạm vi công cộng —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:Sung_Man_Cho_(Ho_Chi_Minh)_1931.jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
              <p>
                Ngày 6-6-1931, Bác bị cảnh sát Anh bắt tại Hồng Kông dưới cái tên{" "}
                <strong>Tống Văn Sơ</strong>, giữa lúc nhà cầm quyền Pháp ở Đông Dương đã kết án tử
                hình vắng mặt Nguyễn Ái Quốc. Luật sư Frank Loseby nhận bào chữa không lấy tiền, đưa vụ
                án ra tới Hội đồng Cơ mật Hoàng gia Anh ở London và thắng. Đầu năm 1933 Bác được trả tự
                do, bí mật rời Hồng Kông; một thời gian sau đó, báo chí — và cả Quốc tế Cộng sản — vẫn
                tưởng Bác đã chết vì bệnh lao trong tù.
              </p>
              <p>
                Từ 1934 đến 1938 Bác ở Liên Xô, học và làm nghiên cứu sinh tại Trường Quốc tế Lênin và
                Viện Nghiên cứu các vấn đề dân tộc và thuộc địa. Cuối năm 1938 Bác trở lại Trung Quốc,
                hoạt động trong hàng ngũ Bát lộ quân ở Quế Lâm, Diên An, rồi lần xuống Côn Minh, Quảng
                Tây — mỗi bước một gần biên giới hơn.
              </p>
            </div>

            <div className="ch rv">
              <span className="yrs">1941 — 1945</span>
              <h3>Pác Bó, Việt Minh, và ngày mồng Hai tháng Chín</h3>
            </div>
            <div className="chunk rv">
              <p>
                Ngày <strong>28-1-1941</strong>, sau ba mươi năm, Bác đặt chân trở lại đất nước ở cột
                mốc 108 trên biên giới Cao Bằng và về ở hang Cốc Bó, Pác Bó, huyện Hà Quảng. Từ 10 đến
                19-5-1941, ngay tại đó, Bác triệu tập và chủ trì Hội nghị lần thứ tám Ban Chấp hành
                Trung ương Đảng — hội nghị đặt nhiệm vụ giải phóng dân tộc lên trên hết thảy, tạm gác
                khẩu hiệu cách mạng ruộng đất, và lập <strong>Việt Nam Độc lập Đồng minh</strong>, gọi
                tắt là <strong>Việt Minh</strong>. Báo <em>Việt Nam độc lập</em> ra đời; ngày
                22-12-1944, theo chỉ thị của Bác, Đội Việt Nam Tuyên truyền Giải phóng quân được thành
                lập.
              </p>
              <figure className="fig land">
                <img src={`${IMG}/hang-coc-bo.jpg`} alt="Cửa hang Cốc Bó ở Pác Bó, Cao Bằng" loading="lazy" />
                <figcaption>
                  <span className="yr">Hang Cốc Bó, Cao Bằng</span>Chỗ ở của Bác trong bảy tuần đầu sau
                  ngày về nước, tháng 2 và 3-1941: một hang đá ẩm bên suối, giường là tấm ván kê trên
                  đá.
                  <span className="cr">
                    Ảnh: Tycho (shansov.net) · CC BY-SA 3.0 —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:C%E1%BB%91c_B%C3%B3.jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
              <figure className="fig right doc">
                <img
                  src={`${IMG}/vong-nguyet.jpg`}
                  alt="Bài thơ Vọng nguyệt trong Ngục trung nhật ký, viết bằng chữ Hán"
                  loading="lazy"
                />
                <figcaption>
                  <span className="yr">1942 – 1943</span>
                  <em>Vọng nguyệt</em> — “Ngắm trăng”, một trong những bài thơ chữ Hán Bác viết trong
                  nhà lao Quảng Tây.
                  <span className="cr">
                    Thư pháp · phạm vi công cộng —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:H%E1%BB%93_Ch%C3%AD_Minh_%E2%80%93_V%E1%BB%8Dng_nguy%E1%BB%87t_(%E6%9C%9B%E6%9C%88),_Ng%E1%BB%A5c_trung_nh%E1%BA%ADt_k%C3%BD_(%E7%8D%84%E4%B8%AD%E6%97%A5%E8%A8%98).jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
              <p>
                Tháng 8-1942, với một cái tên mới — <strong>Hồ Chí Minh</strong> — Bác sang Trung Quốc
                tìm liên lạc với lực lượng Đồng minh, và bị chính quyền Tưởng Giới Thạch bắt ở Túc
                Vinh, Quảng Tây. Mười ba tháng, hơn ba mươi nhà lao của mười ba huyện, tay chân bị
                xiềng, tóc bạc đi vì ghẻ lở và đói. Trong những ngày ấy Bác viết <em>Ngục trung nhật ký</em>{" "}
                — <strong>Nhật ký trong tù</strong> — hơn một trăm ba mươi bài thơ chữ Hán trên một
                cuốn sổ tay nhỏ. Ngày 10-9-1943 Bác được trả tự do.
              </p>
              <p>
                Tháng 8-1945, phát xít Nhật đầu hàng Đồng minh. Thời cơ mà Bác chờ suốt ba mươi tư năm
                đã đến, và nó chỉ kéo dài vài tuần. Quốc dân Đại hội họp ở Tân Trào ngày 16-8-1945 tán
                thành lệnh Tổng khởi nghĩa; trong thư gửi đồng bào cả nước, Bác viết: “Giờ quyết định
                cho vận mệnh dân tộc ta đã đến. Toàn quốc đồng bào hãy đứng dậy đem sức ta mà tự giải
                phóng cho ta.” Mười lăm ngày sau, chính quyền về tay nhân dân trên cả nước.
              </p>
              <p>
                Chiều <strong>2-9-1945</strong>, tại Quảng trường Ba Đình, trước hàng chục vạn người,
                Bác đọc bản <em>Tuyên ngôn Độc lập</em> — bản văn mở đầu bằng chính những lời trong
                Tuyên ngôn Độc lập 1776 của nước Mỹ và Tuyên ngôn Nhân quyền và Dân quyền 1791 của Cách
                mạng Pháp. Giữa chừng, Bác dừng lại hỏi một câu mà những người có mặt hôm đó nhớ suốt
                đời: “Tôi nói, đồng bào nghe rõ không?”
              </p>
            </div>

            <div className="row big2 wide rv">
              <figure className="fig land">
                <img src={`${IMG}/ba-dinh-1945.jpg`} alt="Quảng trường Ba Đình ngày 2-9-1945" loading="lazy" />
                <figcaption>
                  <span className="yr">2-9-1945</span>Quảng trường Ba Đình buổi chiều hôm ấy: lễ đài
                  dựng bằng gỗ, và mấy chục vạn người từ các cửa ô đổ về nghe một cái tên lần đầu được
                  xướng lên trước cả nước.
                  <span className="cr">
                    Ảnh khuyết danh · phạm vi công cộng —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:Ba_Dinh_Square_September_2nd,_1945.jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
              <figure className="fig">
                <img
                  src={`${IMG}/ho-chi-minh-vo-nguyen-giap-1945.jpg`}
                  alt="Chủ tịch Hồ Chí Minh và Võ Nguyên Giáp tại Quảng trường Ba Đình ngày 2-9-1945"
                  loading="lazy"
                />
                <figcaption>
                  <span className="yr">2-9-1945</span>Chủ tịch Hồ Chí Minh và Võ Nguyên Giáp trên lễ
                  đài.
                  <span className="cr">
                    Ảnh: Võ An Ninh · phạm vi công cộng —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:Ho_Chi_Minh_and_Vo_Nguyen_Giap,_Sept._2,_1945.jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
            </div>

            <div className="chunk rv">
              <figure className="pull">
                <blockquote>
                  Nước Việt Nam có quyền hưởng tự do và độc lập, và sự thật đã thành một nước tự do độc
                  lập. Toàn thể dân tộc Việt Nam quyết đem tất cả tinh thần và lực lượng, tính mạng và
                  của cải để giữ vững quyền tự do, độc lập ấy.
                </blockquote>
                <cite>
                  Đoạn kết <em>Tuyên ngôn Độc lập</em>, Quảng trường Ba Đình, ngày 2-9-1945
                </cite>
              </figure>
            </div>

            <div className="ch rv">
              <span className="yrs">1945 — 1954</span>
              <h3>Giặc đói, giặc dốt và chín năm kháng chiến</h3>
            </div>
            <div className="chunk rv">
              <p>
                Nhà nước non trẻ ra đời với ngân khố gần như trống rỗng, hai triệu người vừa chết đói,
                hơn chín mươi phần trăm dân số mù chữ và quân đội nước ngoài ở cả hai đầu đất nước.
                Ngay phiên họp đầu tiên của Chính phủ lâm thời ngày 3-9-1945, Chủ tịch Hồ Chí Minh nêu
                sáu nhiệm vụ cấp bách: cứu đói bằng tăng gia sản xuất và hũ gạo tiết kiệm, mở chiến
                dịch chống nạn mù chữ, tổ chức sớm Tổng tuyển cử theo chế độ phổ thông đầu phiếu, bỏ
                thuế thân, thực hiện tín ngưỡng tự do. Ngày 6-1-1946, cuộc Tổng tuyển cử đầu tiên trong
                lịch sử nước ta bầu ra Quốc hội khóa I.
              </p>
              <p>
                Suốt năm 1946 Bác tìm mọi cách kéo dài hòa bình: ký Hiệp định Sơ bộ ngày 6-3, sang Pháp
                bốn tháng dự Hội nghị Fontainebleau, rồi ký bản Tạm ước ngày 14-9 khi hội nghị thất
                bại. Khi hòa hoãn không còn giữ được nữa, đêm 19-12-1946, lời kêu gọi của Bác được
                truyền đi khắp nước:
              </p>
              <figure className="pull">
                <blockquote>
                  Không! Chúng ta thà hy sinh tất cả, chứ nhất định không chịu mất nước, nhất định
                  không chịu làm nô lệ.
                </blockquote>
                <cite>
                  <em>Lời kêu gọi toàn quốc kháng chiến</em>, ngày 19-12-1946
                </cite>
              </figure>
              <p>
                Chín năm sau đó Bác sống ở Việt Bắc, trong những lán nứa dựng bên suối, di chuyển liên
                tục. Tháng 2-1951, Đại hội lần thứ II của Đảng bầu Bác làm Chủ tịch Ban Chấp hành Trung
                ương. Cuối năm 1953, Bác cùng Bộ Chính trị quyết định mở chiến dịch Điện Biên Phủ và
                trao cho Đại tướng Võ Nguyên Giáp toàn quyền quyết định ở mặt trận. Ngày 7-5-1954, tập
                đoàn cứ điểm Điện Biên Phủ thất thủ; Hiệp định Genève được ký ngày 21-7-1954. Tháng
                10-1954, Bác cùng Trung ương trở về Hà Nội — thủ đô mà Bác đã rời đi tám năm trước.
              </p>
            </div>

            <div className="row c2 wide rv">
              <figure className="fig land">
                <img
                  src={`${IMG}/phan-ke-an-ky-hoa-1948.jpg`}
                  alt="Hoạ sĩ Phan Kế An ký hoạ chân dung Chủ tịch Hồ Chí Minh, tháng 11-1948"
                  loading="lazy"
                />
                <figcaption>
                  <span className="yr">Tháng 11-1948</span>Hoạ sĩ Phan Kế An ngồi ký hoạ Bác giữa chiến
                  khu Việt Bắc — ba tuần sống cạnh nhau để vẽ một bức chân dung.
                  <span className="cr">
                    Ảnh khuyết danh · phạm vi công cộng —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:Painter_Phan_K%E1%BA%BF_An_sketched_a_portrait_of_President_H%E1%BB%93_Ch%C3%AD_Minh,_November_1948.jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
              <figure className="fig land">
                <img
                  src={`${IMG}/chan-dung-but-tich-1950.jpg`}
                  alt="Chân dung Chủ tịch Hồ Chí Minh có bút tích tặng ông Hà Văn Lâu, tháng 5-1950"
                  loading="lazy"
                />
                <figcaption>
                  <span className="yr">Tháng 5-1950</span>Chân dung có bút tích Bác đề tặng ông Hà Văn
                  Lâu — một kiểu quà thường thấy của Bác với cán bộ, chiến sĩ.
                  <span className="cr">
                    Ảnh khuyết danh · phạm vi công cộng —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:Ch%C3%A2n_dung_Ch%E1%BB%A7_t%E1%BB%8Bch_H%E1%BB%93_Ch%C3%AD_Minh_c%C3%B3_b%C3%BAt_t%C3%ADch_c%E1%BB%A7a_ng%C6%B0%E1%BB%9Di_t%E1%BA%B7ng_%C3%B4ng_H%C3%A0_V%C4%83n_L%C3%A2u_th%C3%A1ng_5-1950.jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
            </div>

            <div className="ch rv">
              <span className="yrs">1954 — 1969</span>
              <h3>Nửa nước hòa bình, nửa nước chiến tranh</h3>
            </div>
            <div className="chunk rv">
              <figure className="fig right">
                <img
                  src={`${IMG}/chan-dung-thap-nien-1950.jpg`}
                  alt="Chủ tịch Hồ Chí Minh những năm 1950"
                  loading="lazy"
                />
                <figcaption>
                  <span className="yr">Những năm 1950</span>Bộ kaki bạc màu và chòm râu đã thành hình
                  ảnh quen thuộc của Bác trong mắt cả nước.
                  <span className="cr">
                    Ảnh khuyết danh · phạm vi công cộng —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:H%E1%BB%93_Ch%C3%AD_Minh_1950s.jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
              <p>
                Hiệp định Genève chia đất nước ở vĩ tuyến 17 và hẹn tổng tuyển cử sau hai năm; cuộc
                tổng tuyển cử ấy không bao giờ diễn ra. Mười lăm năm cuối đời của Bác là mười lăm năm
                gánh hai việc cùng lúc: xây dựng miền Bắc và giữ lấy hy vọng thống nhất. Đại hội lần
                thứ III của Đảng (9-1960) xác định hai nhiệm vụ chiến lược ấy; Bác tóm lại bằng một câu
                ngắn — “Nước Việt Nam là một, dân tộc Việt Nam là một.”
              </p>
              <p>
                Ở Hà Nội, Bác không ở trong Phủ Chủ tịch mà dựng một ngôi nhà sàn gỗ hai gian bên bờ ao
                trong khuôn viên, sống với vài bộ quần áo kaki và đôi dép cao su. Bác đi thăm hợp tác xã, công trường, lớp bình dân học vụ, đơn vị bộ đội; phát động Tết trồng cây từ năm
                1959; viết hàng nghìn bài báo ngắn ký nhiều bút danh khác nhau.
              </p>
            </div>

            <div className="row c2 wide rv">
              <figure className="fig land">
                <img src={`${IMG}/tuoi-cay.jpg`} alt="Chủ tịch Hồ Chí Minh tưới cây" loading="lazy" />
                <figcaption>
                  <span className="yr">Trước 1969</span>Tưới cây trong vườn Phủ Chủ tịch. Tết trồng cây
                  do Bác phát động từ năm 1959 đến nay vẫn giữ, mỗi mùa xuân.
                  <span className="cr">
                    Ảnh khuyết danh · phạm vi công cộng —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:UncleHo.jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
              <figure className="fig land">
                <img
                  src={`${IMG}/voi-thieu-nhi.jpg`}
                  alt="Chủ tịch Hồ Chí Minh với thiếu nhi, thập niên 1950"
                  loading="lazy"
                />
                <figcaption>
                  <span className="yr">Thập niên 1950</span>Với thiếu nhi — chủ đề trở đi trở lại trong
                  thư từ, thơ và những buổi đi cơ sở của Bác suốt hai mươi năm cuối đời.
                  <span className="cr">
                    Ảnh: Musée Annam · phạm vi công cộng —{" "}
                    <a
                      href="https://commons.wikimedia.org/wiki/File:Ho-chi-Minh_with_children_(2).jpg"
                      target="_blank"
                      rel="noopener"
                    >
                      Commons
                    </a>
                  </span>
                </figcaption>
              </figure>
            </div>

            <div className="chunk rv">
              <p>
                Từ năm 1965, máy bay Mỹ ném bom miền Bắc. Ngày 17-7-1966, giữa lúc chiến tranh phá hoại
                ác liệt nhất, Bác ra lời kêu gọi trên Đài Tiếng nói Việt Nam:
              </p>
              <figure className="pull">
                <blockquote>
                  Chiến tranh có thể kéo dài 5 năm, 10 năm, 20 năm hoặc lâu hơn nữa… Song nhân dân Việt
                  Nam quyết không sợ! Không có gì quý hơn độc lập, tự do.
                </blockquote>
                <cite>
                  <em>Lời kêu gọi</em> đăng báo <em>Nhân Dân</em> số 4484, ngày 17-7-1966
                </cite>
              </figure>
            </div>

            <div className="ch rv">
              <span className="yrs">1965 — 1969</span>
              <h3>Bản di chúc</h3>
            </div>
            <div className="chunk rv">
              <p>
                Ngày 10-5-1965, khi vừa bước sang tuổi bảy mươi lăm, Bác bắt đầu viết một tài liệu ghi
                ngoài bì là “Tuyệt đối bí mật”. Mỗi tháng Năm những năm sau đó, Bác lại mở ra đọc lại,
                sửa chữa, viết thêm — lần cuối vào tháng 5-1969. Bản <strong>Di chúc</strong> ấy dặn
                việc Đảng, việc đoàn kết, việc chăm lo cho thương binh, cho nông dân, cho thanh niên,
                và dặn cả chuyện tang lễ của mình sao cho đừng tốn kém thì giờ và tiền bạc của dân.
              </p>
              <figure className="pull">
                <blockquote>
                  Điều mong muốn cuối cùng của tôi là: Toàn Đảng, toàn dân ta đoàn kết phấn đấu, xây
                  dựng một nước Việt Nam hòa bình, thống nhất, độc lập, dân chủ và giàu mạnh, và góp
                  phần xứng đáng vào sự nghiệp cách mạng thế giới.
                </blockquote>
                <cite>
                  <em>Di chúc</em>, viết từ năm 1965, sửa lần cuối tháng 5-1969
                </cite>
              </figure>
              <p>
                Chín giờ bốn mươi bảy phút sáng <strong>2-9-1969</strong>, Chủ tịch Hồ Chí Minh qua đời
                tại Hà Nội, thọ bảy mươi chín tuổi — đúng hai mươi tư năm sau ngày Bác đứng đọc Tuyên
                ngôn Độc lập trên chính Quảng trường Ba Đình. Ngày đất nước thống nhất khi ấy còn cách
                gần sáu năm nữa. Năm 1987, Tổ chức Giáo dục, Khoa học và Văn hóa Liên hợp quốc (UNESCO)
                thông qua nghị quyết ghi nhận Hồ Chí Minh là Anh hùng giải phóng dân tộc và Nhà văn hóa
                kiệt xuất của Việt Nam.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section id="biennien">
        <div className="wrap">
          <div className="sec-head rv">
            <span className="sec-num">02</span>
            <h2>Biên niên rút gọn</h2>
            <p className="note">Những mốc chính của một đời người, đọc trong một phút.</p>
          </div>
          <div className="rail">
            <article className="ev key rv">
              <div className="when">
                1890<small>19 tháng 5</small>
              </div>
              <h4>Nguyễn Sinh Cung sinh tại làng Hoàng Trù, Nam Đàn, Nghệ An</h4>
            </article>

            <article className="ev rv">
              <div className="when">1910</div>
              <h4>Dạy chữ Quốc ngữ và thể dục tại Trường Dục Thanh, Phan Thiết</h4>
            </article>

            <article className="ev key rv">
              <div className="when">
                1911<small>5 tháng 6</small>
              </div>
              <h4>Rời bến Nhà Rồng với tên Văn Ba, bắt đầu ba mươi năm xa nước</h4>
            </article>

            <article className="ev rv">
              <div className="when">
                1919<small>18 tháng 6</small>
              </div>
              <h4>
                Gửi <em>Yêu sách của nhân dân An Nam</em> tới Hội nghị Versailles, ký tên Nguyễn Ái
                Quốc
              </h4>
            </article>

            <article className="ev key rv">
              <div className="when">
                1920<small>tháng 7</small>
              </div>
              <h4>Đọc Luận cương của Lênin về vấn đề dân tộc và vấn đề thuộc địa</h4>
            </article>

            <article className="ev rv">
              <div className="when">
                1920<small>tháng 12</small>
              </div>
              <h4>Dự Đại hội Tours, tham gia sáng lập Đảng Cộng sản Pháp</h4>
            </article>

            <article className="ev rv">
              <div className="when">
                1922<small>1 tháng 4</small>
              </div>
              <h4>
                Ra báo <em>Le Paria</em> — Người cùng khổ — tại Paris
              </h4>
            </article>

            <article className="ev rv">
              <div className="when">
                1923<small>tháng 6</small>
              </div>
              <h4>Bí mật rời Paris sang Mátxcơva</h4>
            </article>

            <article className="ev key rv">
              <div className="when">
                1925<small>tháng 6</small>
              </div>
              <h4>
                Lập Hội Việt Nam Cách mạng Thanh niên tại Quảng Châu, ra báo <em>Thanh niên</em>
              </h4>
            </article>

            <article className="ev rv">
              <div className="when">1927</div>
              <h4>
                Xuất bản <em>Đường Kách mệnh</em>
              </h4>
            </article>

            <article className="ev key rv">
              <div className="when">
                1930<small>3 tháng 2</small>
              </div>
              <h4>Chủ trì hội nghị hợp nhất tại Hương Cảng, thành lập Đảng Cộng sản Việt Nam</h4>
            </article>

            <article className="ev rv">
              <div className="when">
                1931<small>6 tháng 6</small>
              </div>
              <h4>Bị bắt ở Hồng Kông với tên Tống Văn Sơ; được trả tự do đầu năm 1933</h4>
            </article>

            <article className="ev key rv">
              <div className="when">
                1941<small>28 tháng 1</small>
              </div>
              <h4>Về nước ở cột mốc 108, Cao Bằng, sau ba mươi năm</h4>
            </article>

            <article className="ev rv">
              <div className="when">
                1941<small>tháng 5</small>
              </div>
              <h4>Chủ trì Hội nghị Trung ương lần thứ tám tại Pác Bó, lập Mặt trận Việt Minh</h4>
            </article>

            <article className="ev rv">
              <div className="when">
                1942<small>tháng 8</small>
              </div>
              <h4>
                Bị chính quyền Tưởng Giới Thạch giam ở Quảng Tây, viết <em>Nhật ký trong tù</em>
              </h4>
            </article>

            <article className="ev key rv">
              <div className="when">
                1945<small>2 tháng 9</small>
              </div>
              <h4>
                Đọc <em>Tuyên ngôn Độc lập</em> tại Quảng trường Ba Đình
              </h4>
            </article>

            <article className="ev key rv">
              <div className="when">
                1946<small>19 tháng 12</small>
              </div>
              <h4>
                Ra <em>Lời kêu gọi toàn quốc kháng chiến</em>
              </h4>
            </article>

            <article className="ev rv">
              <div className="when">
                1954<small>7 tháng 5</small>
              </div>
              <h4>Chiến thắng Điện Biên Phủ; tháng 10 trở về Hà Nội</h4>
            </article>

            <article className="ev rv">
              <div className="when">
                1966<small>17 tháng 7</small>
              </div>
              <h4>“Không có gì quý hơn độc lập, tự do”</h4>
            </article>

            <article className="ev key rv">
              <div className="when">
                1969<small>2 tháng 9</small>
              </div>
              <h4>Chủ tịch Hồ Chí Minh qua đời tại Hà Nội</h4>
            </article>
          </div>
        </div>
      </section>

      <footer>
        <div className="wrap">
          <p>
            Ảnh và tư liệu từ Wikimedia Commons — phạm vi công cộng hoặc giấy phép Creative Commons;
            tác giả và giấy phép ghi ở từng chú thích, kèm liên kết tới trang tệp gốc.
          </p>
          <p>
            Biên soạn theo <em>Hồ Chí Minh — Tiểu sử</em> (Bảo tàng Hồ Chí Minh, Nxb Chính trị quốc
            gia, 2008), <em>Hồ Chí Minh toàn tập</em> và <em>Hồ Chí Minh — Biên niên tiểu sử</em>.
          </p>
        </div>
      </footer>
    </>
  );
}
