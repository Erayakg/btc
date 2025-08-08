#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def clean_accounts():
    """
    Temizlenmiş hesap verilerini oluşturur.
    Sadece kullanıcı adı ve şifre bilgilerini : ile ayırarak kaydeder.
    """
    
    # Orijinal hesap verileri
    accounts_data = """
    KULLANICIADI: kamalaboelkamal ŞİFRE: fIVrAUKckT MAIL: mirandayanez1992@aceomail.com ŞİFRE: wvqtjwalA5835
    KULLANICIADI: shenlongju ŞİFRE: pDlDpJDbgs MAIL: cindyleal1962@bolivianomail.com ŞİFRE: lhfjetfgY7791
    KULLANICIADI: Unknown82497814 ŞİFRE: XCOhwdksjH MAIL: samuelsanders2016@bolivianomail.com ŞİFRE: nhicrpdlS3740
    KULLANICIADI: dupreezp ŞİFRE: UlpxGXiWRs MAIL: peggymartin1959@atorymail.com ŞİFRE: qoimhuvcA1098
    """
    
    # Temizlenmiş hesapları saklamak için liste
    cleaned_accounts = []
    
    # Her satırı işle
    lines = accounts_data.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # KULLANICIADI: ve ŞİFRE: etiketlerini bul ve değerlerini al
        if 'KULLANICIADI:' in line and 'ŞİFRE:' in line:
            # KULLANICIADI: etiketinden sonraki değeri al
            username_start = line.find('KULLANICIADI:') + len('KULLANICIADI:')
            username_end = line.find('ŞİFRE:', username_start)
            username = line[username_start:username_end].strip()
            
            # İlk ŞİFRE: etiketinden sonraki değeri al (mail şifresini değil)
            password_start = line.find('ŞİFRE:', username_end) + len('ŞİFRE:')
            password_end = line.find('MAIL:', password_start)
            if password_end == -1:  # MAIL: yoksa satırın sonuna kadar al
                password = line[password_start:].strip()
            else:
                password = line[password_start:password_end].strip()
            
            # Temizlenmiş format: kullanıcı_adı:şifre
            cleaned_account = f"{username}:{password}"
            cleaned_accounts.append(cleaned_account)
    
    # Temizlenmiş hesapları dosyaya yaz
    with open('cleaned_accounts.txt', 'w', encoding='utf-8') as f:
        for account in cleaned_accounts:
            f.write(account + '\n')
    
    print("Hesaplar temizlendi ve 'cleaned_accounts.txt' dosyasına kaydedildi.")
    print("\nTemizlenmiş hesaplar:")
    for account in cleaned_accounts:
        print(account)

if __name__ == "__main__":
    clean_accounts() 