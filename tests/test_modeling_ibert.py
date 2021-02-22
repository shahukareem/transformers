# coding=utf-8
# Copyright 2020 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import copy
import unittest

from transformers import is_torch_available
from transformers.testing_utils import require_torch, slow, torch_device

from .test_configuration_common import ConfigTester
from .test_generation_utils import GenerationTesterMixin
from .test_modeling_common import ModelTesterMixin, floats_tensor, ids_tensor, random_attention_mask


if is_torch_available():
    import torch

    from transformers.models.ibert.modeling_ibert import (
        IBERT_PRETRAINED_MODEL_ARCHIVE_LIST,
        IBertConfig,
        IBertEmbeddings,
        IBertForMaskedLM,
        IBertForMultipleChoice,
        IBertForQuestionAnswering,
        IBertForSequenceClassification,
        IBertForTokenClassification,
        IBertModel,
        IntGELU,
        IntLayerNorm,
        IntSoftmax,
        QuantAct,
        QuantEmbedding,
        QuantLinear,
        create_position_ids_from_input_ids,
    )


class IBertModelTester:
    def __init__(
        self,
        parent,
    ):
        self.parent = parent
        self.batch_size = 13
        self.seq_length = 7
        self.is_training = True
        self.use_input_mask = True
        self.use_token_type_ids = True
        self.use_labels = True
        self.vocab_size = 99
        self.hidden_size = 32
        self.num_hidden_layers = 5
        self.num_attention_heads = 4
        self.intermediate_size = 37
        self.hidden_act = "gelu"
        self.hidden_dropout_prob = 0.1
        self.attention_probs_dropout_prob = 0.1
        self.max_position_embeddings = 512
        self.type_vocab_size = 16
        self.type_sequence_label_size = 2
        self.initializer_range = 0.02
        self.num_labels = 3
        self.num_choices = 4
        self.scope = None

    def prepare_config_and_inputs(self):
        input_ids = ids_tensor([self.batch_size, self.seq_length], self.vocab_size)

        input_mask = None
        if self.use_input_mask:
            input_mask = random_attention_mask([self.batch_size, self.seq_length])

        token_type_ids = None
        if self.use_token_type_ids:
            token_type_ids = ids_tensor([self.batch_size, self.seq_length], self.type_vocab_size)

        sequence_labels = None
        token_labels = None
        choice_labels = None
        if self.use_labels:
            sequence_labels = ids_tensor([self.batch_size], self.type_sequence_label_size)
            token_labels = ids_tensor([self.batch_size, self.seq_length], self.num_labels)
            choice_labels = ids_tensor([self.batch_size], self.num_choices)

        config = IBertConfig(
            vocab_size=self.vocab_size,
            hidden_size=self.hidden_size,
            num_hidden_layers=self.num_hidden_layers,
            num_attention_heads=self.num_attention_heads,
            intermediate_size=self.intermediate_size,
            hidden_act=self.hidden_act,
            hidden_dropout_prob=self.hidden_dropout_prob,
            attention_probs_dropout_prob=self.attention_probs_dropout_prob,
            max_position_embeddings=self.max_position_embeddings,
            type_vocab_size=self.type_vocab_size,
            initializer_range=self.initializer_range,
            quant_mode=True,  # TODO add False as well
        )

        return config, input_ids, token_type_ids, input_mask, sequence_labels, token_labels, choice_labels

    def create_and_check_model(
        self, config, input_ids, token_type_ids, input_mask, sequence_labels, token_labels, choice_labels
    ):
        model = IBertModel(config=config)
        model.to(torch_device)
        model.eval()
        result = model(input_ids, attention_mask=input_mask, token_type_ids=token_type_ids)
        result = model(input_ids, token_type_ids=token_type_ids)
        result = model(input_ids)

        self.parent.assertEqual(result.last_hidden_state.shape, (self.batch_size, self.seq_length, self.hidden_size))
        self.parent.assertEqual(result.pooler_output.shape, (self.batch_size, self.hidden_size))

    def create_and_check_for_masked_lm(
        self, config, input_ids, token_type_ids, input_mask, sequence_labels, token_labels, choice_labels
    ):
        model = IBertForMaskedLM(config=config)
        model.to(torch_device)
        model.eval()
        result = model(input_ids, attention_mask=input_mask, token_type_ids=token_type_ids, labels=token_labels)
        self.parent.assertEqual(result.logits.shape, (self.batch_size, self.seq_length, self.vocab_size))

    def create_and_check_for_token_classification(
        self, config, input_ids, token_type_ids, input_mask, sequence_labels, token_labels, choice_labels
    ):
        config.num_labels = self.num_labels
        model = IBertForTokenClassification(config=config)
        model.to(torch_device)
        model.eval()
        result = model(input_ids, attention_mask=input_mask, token_type_ids=token_type_ids, labels=token_labels)
        self.parent.assertEqual(result.logits.shape, (self.batch_size, self.seq_length, self.num_labels))

    def create_and_check_for_multiple_choice(
        self, config, input_ids, token_type_ids, input_mask, sequence_labels, token_labels, choice_labels
    ):
        config.num_choices = self.num_choices
        model = IBertForMultipleChoice(config=config)
        model.to(torch_device)
        model.eval()
        multiple_choice_inputs_ids = input_ids.unsqueeze(1).expand(-1, self.num_choices, -1).contiguous()
        multiple_choice_token_type_ids = token_type_ids.unsqueeze(1).expand(-1, self.num_choices, -1).contiguous()
        multiple_choice_input_mask = input_mask.unsqueeze(1).expand(-1, self.num_choices, -1).contiguous()
        result = model(
            multiple_choice_inputs_ids,
            attention_mask=multiple_choice_input_mask,
            token_type_ids=multiple_choice_token_type_ids,
            labels=choice_labels,
        )
        self.parent.assertEqual(result.logits.shape, (self.batch_size, self.num_choices))

    def create_and_check_for_question_answering(
        self, config, input_ids, token_type_ids, input_mask, sequence_labels, token_labels, choice_labels
    ):
        model = IBertForQuestionAnswering(config=config)
        model.to(torch_device)
        model.eval()
        result = model(
            input_ids,
            attention_mask=input_mask,
            token_type_ids=token_type_ids,
            start_positions=sequence_labels,
            end_positions=sequence_labels,
        )
        self.parent.assertEqual(result.start_logits.shape, (self.batch_size, self.seq_length))
        self.parent.assertEqual(result.end_logits.shape, (self.batch_size, self.seq_length))

    def prepare_config_and_inputs_for_common(self):
        config_and_inputs = self.prepare_config_and_inputs()
        (
            config,
            input_ids,
            token_type_ids,
            input_mask,
            sequence_labels,
            token_labels,
            choice_labels,
        ) = config_and_inputs
        inputs_dict = {"input_ids": input_ids, "token_type_ids": token_type_ids, "attention_mask": input_mask}
        return config, inputs_dict


@require_torch
class IBertModelTest(ModelTesterMixin, GenerationTesterMixin, unittest.TestCase):

    test_pruning = False
    test_torchscript = False
    test_head_masking = False
    test_resize_embeddings = False
    is_encoder_decoder = False

    all_model_classes = (
        (
            IBertForMaskedLM,
            IBertModel,
            IBertForSequenceClassification,
            IBertForTokenClassification,
            IBertForMultipleChoice,
            IBertForQuestionAnswering,
        )
        if is_torch_available()
        else ()
    )

    def setUp(self):
        self.model_tester = IBertModelTester(self)
        self.config_tester = ConfigTester(self, config_class=IBertConfig, hidden_size=37)

    def test_config(self):
        self.config_tester.run_common_tests()

    def test_model(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        self.model_tester.create_and_check_model(*config_and_inputs)

    def test_model_various_embeddings(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        # I-BERT only supports absolute embedding
        for type in ["absolute"]:
            config_and_inputs[0].position_embedding_type = type
            self.model_tester.create_and_check_model(*config_and_inputs)

    def test_for_masked_lm(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        self.model_tester.create_and_check_for_masked_lm(*config_and_inputs)

    def test_for_token_classification(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        self.model_tester.create_and_check_for_token_classification(*config_and_inputs)

    def test_for_multiple_choice(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        self.model_tester.create_and_check_for_multiple_choice(*config_and_inputs)

    def test_for_question_answering(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        self.model_tester.create_and_check_for_question_answering(*config_and_inputs)

    @slow
    def test_model_from_pretrained(self):
        for model_name in ROBERTA_PRETRAINED_MODEL_ARCHIVE_LIST[:1]:
            model = IBertModel.from_pretrained(model_name)
            self.assertIsNotNone(model)

    def test_create_position_ids_respects_padding_index(self):
        """Ensure that the default position ids only assign a sequential . This is a regression
        test for https://github.com/huggingface/transformers/issues/1761

        The position ids should be masked with the embedding object's padding index. Therefore, the
        first available non-padding position index is IBertEmbeddings.padding_idx + 1
        """
        config = self.model_tester.prepare_config_and_inputs()[0]
        model = IBertEmbeddings(config=config)

        input_ids = torch.as_tensor([[12, 31, 13, model.padding_idx]])
        expected_positions = torch.as_tensor(
            [[0 + model.padding_idx + 1, 1 + model.padding_idx + 1, 2 + model.padding_idx + 1, model.padding_idx]]
        )

        position_ids = create_position_ids_from_input_ids(input_ids, model.padding_idx)
        self.assertEqual(position_ids.shape, expected_positions.shape)
        self.assertTrue(torch.all(torch.eq(position_ids, expected_positions)))

    def test_create_position_ids_from_inputs_embeds(self):
        """Ensure that the default position ids only assign a sequential . This is a regression
        test for https://github.com/huggingface/transformers/issues/1761

        The position ids should be masked with the embedding object's padding index. Therefore, the
        first available non-padding position index is IBertEmbeddings.padding_idx + 1
        """
        config = self.model_tester.prepare_config_and_inputs()[0]
        embeddings = IBertEmbeddings(config=config)

        inputs_embeds = torch.Tensor(2, 4, 30)
        expected_single_positions = [
            0 + embeddings.padding_idx + 1,
            1 + embeddings.padding_idx + 1,
            2 + embeddings.padding_idx + 1,
            3 + embeddings.padding_idx + 1,
        ]
        expected_positions = torch.as_tensor([expected_single_positions, expected_single_positions])
        position_ids = embeddings.create_position_ids_from_inputs_embeds(inputs_embeds)
        self.assertEqual(position_ids.shape, expected_positions.shape)
        self.assertTrue(torch.all(torch.eq(position_ids, expected_positions)))

    # Override
    def test_model_common_attributes(self):
        config, inputs_dict = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            model = model_class(config)
            self.assertIsInstance(model.get_input_embeddings(), QuantEmbedding)
            model.set_input_embeddings(torch.nn.Embedding(10, 10))
            x = model.get_output_embeddings()
            self.assertTrue(x is None or isinstance(x, torch.nn.Linear))

    # Override
    def test_feed_forward_chunking(self):
        pass # I-BERT does not support chunking

    # Override
    def test_inputs_embeds(self):
        config, inputs_dict = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            model = model_class(config)
            model.to(torch_device)
            model.eval()

            inputs = copy.deepcopy(self._prepare_for_class(inputs_dict, model_class))

            if not self.is_encoder_decoder:
                input_ids = inputs["input_ids"]
                del inputs["input_ids"]
            else:
                encoder_input_ids = inputs["input_ids"]
                decoder_input_ids = inputs.get("decoder_input_ids", encoder_input_ids)
                del inputs["input_ids"]
                inputs.pop("decoder_input_ids", None)

            wte = model.get_input_embeddings()
            if not self.is_encoder_decoder:
                embed, embed_scaling_factor = wte(input_ids)
                inputs["inputs_embeds"] = embed
            else:
                inputs["inputs_embeds"] = wte(encoder_input_ids)
                inputs["decoder_inputs_embeds"] = wte(decoder_input_ids)

            with torch.no_grad():
                model(**inputs)[0]


@require_torch
class IBertModelIntegrationTest(unittest.TestCase):
    def test_quant_embedding(self):
        weight_bit = 8
        embedding = QuantEmbedding(2, 4, quant_mode=True, weight_bit=weight_bit)
        embedding_weight = torch.tensor(
            [
                [-1.0, -2.0, -3.0, -4.0],
                [
                    5.0,
                    6.0,
                    7.0,
                    8.0,
                ],
            ]
        )
        embedding.weight = torch.nn.Parameter(embedding_weight)

        expected_scaling_factor = embedding_weight.abs().max() / (2 ** (weight_bit - 1) - 1)
        x, x_scaling_factor = embedding(torch.tensor(0))
        y, y_scaling_factor = embedding(torch.tensor(1))

        # scaling factor should follow the symmetric quantization rule
        self.assertTrue(torch.allclose(x_scaling_factor, expected_scaling_factor, atol=1e-4))
        self.assertTrue(torch.allclose(x_scaling_factor, expected_scaling_factor, atol=1e-4))
        self.assertTrue(torch.allclose(y_scaling_factor, expected_scaling_factor, atol=1e-4))

        # quantization error should not exceed the scaling factor
        self.assertTrue(torch.allclose(x, embedding_weight[0], atol=expected_scaling_factor))
        self.assertTrue(torch.allclose(y, embedding_weight[1], atol=expected_scaling_factor))

    def test_quant_act(self):
        def _test_range():
            act = QuantAct(activation_bit, act_range_momentum, quant_mode=True)

            # First pass
            x = torch.tensor(
                [
                    [-1.0, -2.0, -3.0, -4.0],
                    [5.0, 6.0, 7.0, 8.0],
                ]
            )
            x_scaling_factor = torch.tensor(1.0)
            y, y_scaling_factor = act(x, x_scaling_factor)
            y_int = y / y_scaling_factor

            # After the first pass, x_min and x_max should be initialized with x.min() and x.max()
            expected_x_min, expected_x_max = x.min(), x.max()
            self.assertTrue(torch.allclose(act.x_min, expected_x_min, atol=1e-4))
            self.assertTrue(torch.allclose(act.x_max, expected_x_max, atol=1e-4))

            # scaling factor should follow the symmetric quantization rule
            expected_range = torch.max(expected_x_min.abs(), expected_x_max.abs())
            expected_scaling_factor = expected_range / (2 ** (activation_bit - 1) - 1)
            self.assertTrue(torch.allclose(y_scaling_factor, expected_scaling_factor, atol=1e-4))

            # quantization error should not exceed the scaling factor
            self.assertTrue(torch.allclose(x, y, atol=expected_scaling_factor))

            # output should be integer
            self.assertTrue(torch.allclose(y_int, y_int.round(), atol=1e-4))

            # Second Pass
            x = (
                torch.tensor(
                    [
                        [-1.0, -2.0, -3.0, -4.0],
                        [5.0, 6.0, 7.0, 8.0],
                    ]
                )
                * 2
            )
            x_scaling_factor = torch.tensor(1.0)
            y, y_scaling_factor = act(x, x_scaling_factor)
            y_int = y / y_scaling_factor

            # From the second pass, x_min and x_max should be updated with moving average
            expected_x_min = expected_x_min * act_range_momentum + x.min() * (1 - act_range_momentum)
            expected_x_max = expected_x_max * act_range_momentum + x.max() * (1 - act_range_momentum)
            self.assertTrue(torch.allclose(act.x_min, expected_x_min, atol=1e-4))
            self.assertTrue(torch.allclose(act.x_max, expected_x_max, atol=1e-4))

            # scaling factor should follow the symmetric quantization rule
            expected_range = torch.max(expected_x_min.abs(), expected_x_max.abs())
            expected_scaling_factor = expected_range / (2 ** (activation_bit - 1) - 1)
            self.assertTrue(torch.allclose(y_scaling_factor, expected_scaling_factor, atol=1e-4))

            # quantization error should not exceed the scaling factor
            x = x.clamp(min=-expected_range, max=expected_range)
            self.assertTrue(torch.allclose(x, y, atol=expected_scaling_factor))

            # output should be integer
            self.assertTrue(torch.allclose(y_int, y_int.round(), atol=1e-4))

            # Third pass, with eval()
            act.eval()
            x = (
                torch.tensor(
                    [
                        [-1.0, -2.0, -3.0, -4.0],
                        [5.0, 6.0, 7.0, 8.0],
                    ]
                )
                * 3
            )

            # In eval mode, min/max and scaling factor must be fixed
            self.assertTrue(torch.allclose(act.x_min, expected_x_min, atol=1e-4))
            self.assertTrue(torch.allclose(act.x_max, expected_x_max, atol=1e-4))
            self.assertTrue(torch.allclose(y_scaling_factor, expected_scaling_factor, atol=1e-4))

        def _test_identity():
            # test if identity and identity_scaling_factor are given
            # should add the input values
            act = QuantAct(activation_bit, act_range_momentum, quant_mode=True)
            x = torch.tensor([[-1.0, -2.0, -3.0, -4.0], [5.0, 6.0, 7.0, 8.0]])
            y = torch.tensor([[6.0, -7.0, 1.0, -2.0], [3.0, -4.0, -8.0, 5.0]])
            x_scaling_factor = torch.tensor(1.0)
            y_scaling_factor = torch.tensor(0.5)
            z, z_scaling_factor = act(x, x_scaling_factor, y, y_scaling_factor)
            z_int = z / z_scaling_factor
            self.assertTrue(torch.allclose(x + y, z, atol=0.1))
            self.assertTrue(torch.allclose(z_int, z_int.round(), atol=1e-4))

        activation_bit = 8
        act_range_momentum = 0.95
        _test_range()
        _test_identity()

    def test_quant_linear(self):
        def _test(per_channel):
            linear_q = QuantLinear(2, 4, quant_mode=True, per_channel=per_channel, weight_bit=weight_bit)
            linear_dq = QuantLinear(2, 4, quant_mode=False, per_channel=per_channel, weight_bit=weight_bit)
            linear_weight = torch.tensor(
                [
                    [-1.0, 2.0, 3.0, -4.0],
                    [5.0, -6.0, -7.0, 8.0],
                ]
            ).T
            linear_q.weight = torch.nn.Parameter(linear_weight)
            linear_dq.weight = torch.nn.Parameter(linear_weight)

            q, q_scaling_factor = linear_q(x, x_scaling_factor)
            q_int = q / q_scaling_factor
            dq, dq_scaling_factor = linear_dq(x, x_scaling_factor)

            if per_channel:
                q_max = linear_weight.abs().max(dim=1).values
            else:
                q_max = linear_weight.abs().max()
            expected_scaling_factor = q_max / (2 ** (weight_bit - 1) - 1)

            # scaling factor should follow the symmetric quantization rule
            self.assertTrue(torch.allclose(linear_q.fc_scaling_factor, expected_scaling_factor, atol=1e-4))

            # output of the normal linear layer and the quantized linear layer should be similar
            self.assertTrue(torch.allclose(q, dq, atol=0.5))

            # output of the quantized linear layer should be integer
            self.assertTrue(torch.allclose(q_int, q_int.round(), atol=1e-4))

        weight_bit = 8
        x = torch.tensor([[2.0, -5.0], [-3.0, 4.0]])
        x_scaling_factor = torch.tensor([1.0])
        _test(True)
        _test(False)

    def test_int_gelu(self):
        gelu_q = IntGELU(quant_mode=True)
        gelu_dq = torch.nn.GELU()

        x_int = torch.range(-10000, 10000, 1)
        x_scaling_factor = torch.tensor(0.001)
        x = x_int * x_scaling_factor

        q, q_scaling_factor = gelu_q(x, x_scaling_factor)
        q_int = q / q_scaling_factor
        dq = gelu_dq(x)

        # output of the normal GELU and the quantized GELU should be similar
        self.assertTrue(torch.allclose(q, dq, atol=0.5))

        # output of the quantized GELU layer should be integer
        self.assertTrue(torch.allclose(q_int, q_int.round(), atol=1e-4))

    def test_int_softmax(self):
        output_bit = 8
        softmax_q = IntSoftmax(output_bit, quant_mode=True)
        softmax_dq = torch.nn.Softmax()

        # x_int = torch.range(-10000, 10000, 1)
        def _test(array):
            x_int = torch.tensor(array)
            x_scaling_factor = torch.tensor(0.1)
            x = x_int * x_scaling_factor

            q, q_scaling_factor = softmax_q(x, x_scaling_factor)
            q_int = q / q_scaling_factor
            dq = softmax_dq(x)

            # output of the normal Softmax and the quantized Softmax should be similar
            self.assertTrue(torch.allclose(q, dq, atol=0.5))

            # output of the quantized GELU layer should be integer
            self.assertTrue(torch.allclose(q_int, q_int.round(), atol=1e-4))

            # Output of the quantize Softmax should not exceed the output_bit
            self.assertTrue(q.abs().max() < 2 ** output_bit)

        array = [[i + j for j in range(10)] for i in range(-10, 10)]
        _test(array)
        array = [[i + j for j in range(50)] for i in range(-10, 10)]
        _test(array)
        array = [[i + 100 * j for j in range(2)] for i in range(-10, 10)]
        _test(array)

    def test_int_layernorm(self):
        output_bit = 8

        # some random matrix
        array = [[[i * j * j + j for j in range(5, 15)]] for i in range(-10, 10)]
        x_int = torch.tensor(array)
        x_scaling_factor = torch.tensor(0.1)
        x = x_int * x_scaling_factor

        ln_q = IntLayerNorm(x.shape[1:], 1e-5, quant_mode=True, output_bit=output_bit)
        ln_dq = torch.nn.LayerNorm(x.shape[1:], 1e-5)

        ln_q.weight = torch.nn.Parameter(torch.ones(x.shape[1:]))
        ln_q.bias = torch.nn.Parameter(torch.ones(x.shape[1:]))
        ln_dq.weight = torch.nn.Parameter(torch.ones(x.shape[1:]))
        ln_dq.bias = torch.nn.Parameter(torch.ones(x.shape[1:]))

        q, q_scaling_factor = ln_q(x, x_scaling_factor)
        q_int = q / q_scaling_factor
        dq = ln_dq(x)

        # output of the normal LN and the quantized LN should be similar
        self.assertTrue(torch.allclose(q, dq, atol=0.5))

        # output of the quantized GELU layer should be integer
        self.assertTrue(torch.allclose(q_int, q_int.round(), atol=1e-4))