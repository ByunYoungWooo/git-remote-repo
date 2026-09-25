<?php
/**
 * Service: TelegramService
 * .env의 TELEGRAM_BOT_TOKEN 과 TELEGRAM_CHAT_ID 가 설정된 경우에만 발송.
 */
final class TelegramService
{
    public static function send(string $text): bool
    {
        $token = getenv('TELEGRAM_BOT_TOKEN');
        $chatId = getenv('TELEGRAM_CHAT_ID');
        if (!$token || !$chatId) {
            return false;
        }
        $url = "https://api.telegram.org/bot{$token}/sendMessage";
        $data = json_encode([
            'chat_id' => $chatId,
            'text'    => $text,
        ]);
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_POST       => true,
            CURLOPT_POSTFIELDS => $data,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT    => 10,
        ]);
        $res = curl_exec($ch);
        $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        return $code === 200;
    }
}
