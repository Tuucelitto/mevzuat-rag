# Mevzuat Asistanı (RAG)

## Proje hakkında
Türk iş mevzuatı üzerinde çalışan, Türkçe soruları kaynak göstererek yanıtlayan bir RAG sistemi.
Portfolyo projesi; amacı AI/ML iş başvurularında ölçülebilir bir yapay zeka sistemi göstermek.
Farkı: sistemin başarısı test setiyle sayısal olarak ölçülür.

## Benimle çalışma şekli
- Bana Türkçe açıkla. Kod, değişken adları, yorumlar, commit mesajları ve README İngilizce olsun.
- Yapay zekayla proje geliştirmeyi öğreniyorum: kodu anlamak istiyorum. Yeni kavramları kısaca açıkla.
- Büyük işleri küçük adımlara böl, her adımdan sonra kontrol edebileceğim bir noktada dur.
- Yeni paket eklemeden önce neden gerektiğini söyle ve onayımı al.

## Kararlar
- Belgeler: İş Kanunu (4857) ile başla, sonra ilgili mevzuat. Yalnızca herkese açık resmî metinler.
- Backend: Python, FastAPI
- Arayüz: Vue 3, TypeScript
- LLM ve embedding: Gemini API (anahtar yalnızca `.env` içinde)
- Vektör deposu: ilk adımda seçenekleri karşılaştırıp karar ver

## Yol haritası
1. Temel hat: belge yükleme, parçalama, embedding, kaynak gösteren cevap
2. Ölçüm: 30-50 soruluk elle hazırlanmış test seti ve metrikler
3. İyileştirme: parçalama ve arama yöntemlerini karşılaştır, sonuçları sayıyla kaydet
4. Arayüz ve yayın: API, Vue arayüzü, README, portfolyoya kart ekleme

## Kalite kuralları
- Her cevap madde numarasıyla kaynak göstermeli; belgede yoksa "bilmiyorum" demeli, uydurmamalı.
- Arayüzde "hukuki danışmanlık değildir" uyarısı olmalı.
- Metrikler gerçek ölçümlerden gelmeli; README'ye ölçülmemiş sayı yazılmamalı.
- Gizli bilgiler koda yazılmaz, `.env` ve `.gitignore` kullanılır.
- Yayın için önce hedef adresin Türkiye'den açıldığını doğrula (`*.vercel.app`, `*.pages.dev` sorun çıkardı; `*.netlify.app` çalıştı).
