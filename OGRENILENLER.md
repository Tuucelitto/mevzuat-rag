# Öğrendiklerim

Bu projede öğrendiğim teknolojiler ve terimler. Proje bitince tamamlanacak.

## pytest

**Ne?** Python için test yazma ve çalıştırma aracı. Kodun beklenen şekilde çalıştığını elle denemek yerine otomatik olarak kontrol eder.

**Ne için kullanılır?** Küçük `test_*` fonksiyonları yazılır, içlerinde `assert` ile beklenen sonuç belirtilir. `pytest` komutu bu dosyaları bulup hepsini çalıştırır ve hangisinin geçtiğini, hangisinin kaldığını gösterir. Kodu değiştirdikten sonra bir şeyi bozup bozmadığımızı saniyeler içinde görürüz.

```python
def test_toplama():
    assert 2 + 2 == 4
```

**Üç temel kavram:**
- **`assert`:** "Bu doğru olmalı" demektir. Yanlışsa test kalır.
- **Fixture:** Testlerin ortak ihtiyacını hazırlayan fonksiyon; örneğin hazır bir test istemcisi.
- **`parametrize`:** Aynı testi farklı girdilerle çalıştırır; örneğin boş soru ve çok uzun soru.

**Bu projede nasıl kullanıldı?** `tests/test_api.py` FastAPI uç noktalarını `TestClient` ile dener. Gemini yerine sahte cevaplar kullanıldığı için test kota harcamaz, internet gerektirmez ve her seferinde aynı sonucu verir. Sahte saat (`FakeClock`) sayesinde bir gün beklemeden günlük sınırlar da denenir.

**Test ile ölçüm farkı:** `pytest` kodun kurallarının çalıştığını doğrular; örneğin "501 karakterlik soru reddedilir". Sistemin cevaplarının ne kadar iyi olduğunu ise `eval/run_eval.py` ölçer.
