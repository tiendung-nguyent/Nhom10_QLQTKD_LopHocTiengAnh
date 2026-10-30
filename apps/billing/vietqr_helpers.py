import urllib.parse
from datetime import datetime
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

# Cấu hình thông tin tài khoản nhận học phí của Trung tâm Academix
BANK_ID = "VCB"                  # Mã ngân hàng Vietcombank
ACCOUNT_NO = "1023262284"         # Số tài khoản của bạn
ACCOUNT_NAME = "ACADEMIX CENTER"  # Tên chủ tài khoản (viết hoa không dấu)


def generate_vietcombank_qr(amount, content, template="compact"):
    """
    Hàm sinh URL hình ảnh VietQR tự động cho tài khoản Vietcombank.
    - amount: Số tiền học phí (ví dụ: 4500000)
    - content: Nội dung chuyển khoản (ví dụ: 'ACADEMIX HP HV001')
    """
    encoded_content = urllib.parse.quote(str(content))
    encoded_account_name = urllib.parse.quote(ACCOUNT_NAME)
    
    qr_url = (
        f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-{template}.png"
        f"?amount={int(amount)}"
        f"&addInfo={encoded_content}"
        f"&accountName={encoded_account_name}"
    )
    
    return qr_url


def send_payment_success_email(student_email, student_name, invoice_id, amount, payment_content='', classroom_name='', class_schedule='', transaction_code=None):
    """
    Hàm gửi email biên nhận thanh toán học phí thành công cho học viên.
    """
    if transaction_code:
        payment_content = transaction_code
    subject = f"[Academix] Biên nhận thanh toán học phí thành công - Hóa đơn #HD{invoice_id}"
    
    # Định dạng tiền tệ và thời gian
    formatted_amount = f"{int(amount):,}"
    payment_date = datetime.now().strftime("%H:%M - %d/%m/%Y")
    
    context = {
        'student_name': student_name,
        'invoice_id': invoice_id,
        'payment_date': payment_date,
        'amount': formatted_amount,
        'payment_content': payment_content,
        'classroom_name': classroom_name,
        'class_schedule': class_schedule,
    }
    
    # Nội dung văn bản thuần (dự phòng)
    text_content = f"""
    Xin chào {student_name},
    
    Academix xin xác nhận bạn đã thanh toán thành công hóa đơn #HD{invoice_id}.
    - Số tiền: {formatted_amount} VNĐ
    - Thời gian: {payment_date}
    - Lớp học đăng ký: {classroom_name}
    - Lịch học: {class_schedule}
    
    Tài khoản của bạn đã được kích hoạt quyền truy cập lớp học.
    Cảm ơn bạn đã lựa chọn Academix!
    """
    
    # Render giao diện HTML từ template
    html_content = render_to_string('emails/tuition_paid_receipt.html', context)
    
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'Academix English Center <academixenglishcenter@gmail.com>'),
            to=[student_email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return True
    except Exception as e:
        print(f"Lỗi gửi email xác nhận thanh toán: {e}")
        return False
