from __future__ import division
import lib
import numpy as np

class Evaluator(object):
    def __init__(self, model, metrics, dicts, opt, logger=None):
        self.model = model
        self.loss_func = metrics["nmt_loss"]
        self.sent_reward_func = metrics["sent_reward"]
        self.corpus_reward_func = metrics["corp_reward"]
        self.dicts = dicts
        self.max_length = opt.max_predict_length
        self.opt = opt
        self.logger = logger
        if logger is not None:
            self.log = self.logger.log_print

    def eval(self, data, pred_file=None, tgt_file=None):
        self.model.eval()

        total_loss = 0
        total_words = 0
        total_sents = 0
        total_sent_reward = 0

        all_preds = []
        all_targets = []

        # Output the translation and tgt for checking by moses bleu
        if tgt_file is not None:
            for i in range(len(data)):
                batch = data[i]
                targets = batch[1]
                targets = targets.data.t().tolist()
                all_targets.extend(targets)
            self._convert_and_report(data, tgt_file, all_targets, metrics=None)
            return(None)

        for i in range(len(data)):
            batch = data[i]
            targets = batch[1]

            attention_mask = batch[0][0].data.eq(lib.Constants.PAD).t()
            self.model.decoder.attn.applyMask(attention_mask)
            outputs = self.model(batch, True)


            weights = targets.ne(lib.Constants.PAD).float()
            num_words = weights.data.sum()
            _, loss = self.model.predict(outputs, targets, weights, self.loss_func)

            preds = self.model.translate(batch, self.max_length)
            preds = preds.t().tolist()
            targets = targets.data.t().tolist()
            rewards, _ = self.sent_reward_func(preds, targets)
            all_preds.extend(preds)
            all_targets.extend(targets)

            total_loss += loss
            total_words += num_words
            to_add = sum(rewards)
            total_sent_reward += to_add 
            total_sents += batch[1].size(1)

        loss = total_loss / total_words
        sent_reward = total_sent_reward / total_sents
        corpus_reward = self.corpus_reward_func(all_preds, all_targets)

        if pred_file is not None:
            self._convert_and_report(data, pred_file, all_preds,
                (loss, sent_reward, corpus_reward))

        return loss, sent_reward, corpus_reward

    def _convert_and_report(self, data, pred_file, preds, metrics):
        #When -eval
        preds = data.restore_pos(preds)
        with open(pred_file, "w") as f:
            for sent in preds:
                sent = lib.Reward.clean_up_sentence(sent, remove_unk=False, remove_eos=True)
                sent = [self.dicts["tgt"].getLabel(w) for w in sent]
                print(" ".join(sent), file=f)

        if metrics is not None:
            loss, sent_reward, corpus_reward = metrics
            self.log("")
            self.log("Loss: %.6f" % loss)
            self.log("Sentence reward: %.2f" % (sent_reward * 100))
            self.log("Corpus reward: %.2f" % (corpus_reward * 100))
            self.log("Predictions saved to %s" % pred_file)


