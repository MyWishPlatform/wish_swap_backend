from django.db import models


class BotSub(models.Model):
    dex = models.ForeignKey('tokens.Dex', on_delete=models.CASCADE)
    chat_id = models.IntegerField(unique=True)


class BotSwapMessage(models.Model):
    payment = models.ForeignKey('payments.Payment', on_delete=models.CASCADE)
    sub = models.ForeignKey(BotSub, on_delete=models.CASCADE)
    message_id = models.IntegerField()
