#!/usr/bin/env python3
# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import kfp.dsl as dsl
from kfp import gcp


@dsl.pipeline(
  name='Immediate Value',
  description='A pipeline with parameter values hard coded'
)
def immediate_value_pipeline():
  # "url" is a pipeline parameter with value being hard coded.
  # It is useful in case for some component you want to hard code a parameter instead
  # of exposing it as a pipeline parameter.
  src_url=dsl.PipelineParam(name='src_url', value='https://gist.githubusercontent.com/curran/a08a1080b88344b0c8a7/raw/d546eaee765268bf2f487608c537c05e22e4b221/iris.csv')
  gcp_uri=dsl.PipelineParam(name='gcp_uri', value='gs://hackathon-nubank/data.csv')
  gcp_train_uri=dsl.PipelineParam(name='gcp_train_uri', value='gs://hackathon-nubank/data.csv')
  gcp_holdout_uri=dsl.PipelineParam(name='gcp_holdout_uri', value='gs://hackathon-nubank/data.csv')


  fetch = dsl.ContainerOp(
     name='fetch',
     image='google/cloud-sdk:216.0.0',
     command=['sh', '-c'],
     arguments=['''curl %s > /tmp/data.csv;
                   gsutil ls gs://hackathon-nubank;
                   gcloud auth activate-service-account --key-file '/secret/gcp-credentials/user-gcp-sa.json' && gsutil cp /tmp/data.csv %s;
                   echo %s > /tmp/gcp_uri
               ''' % (src_url, gcp_uri, gcp_uri)],
     file_outputs={'uri': '/tmp/gcp_uri'}).apply(gcp.use_gcp_secret('user-gcp-sa'))

  transform_and_split = dsl.ContainerOp(
     name='transform-and-split',
     image='google/cloud-sdk:216.0.0',
     command=['sh', '-c'],
     arguments=['''gcloud auth activate-service-account --key-file '/secret/gcp-credentials/user-gcp-sa.json' && gsutil cp %s /tmp/data.csv;
                   cat /tmp/data.csv;
                   echo "train_uri" > /tmp/train_uri;
                   echo "holdout_uri" > /tmp/holdout_uri;
                   echo "pre_proc_fn_uri" > /tmp/pre_proc_fn_uri
                ''' % fetch.output],
     file_outputs={'train_uri': '/tmp/train_uri',
                   'holdout_uri': '/tmp/holdout_uri',
                   'pre_proc_fn_uri': '/tmp/pre_proc_fn_uri'}).apply(gcp.use_gcp_secret('user-gcp-sa'))

  train = dsl.ContainerOp(
     name='train',
     image='google/cloud-sdk:216.0.0',
     command=['sh', '-c'],
     arguments=['''echo %s;
                   echo "model_pkl" > /tmp/model_pkl
                ''' % transform_and_split.outputs['train_uri']],
     file_outputs={'model_pkl': '/tmp/model_pkl'}).apply(gcp.use_gcp_secret('user-gcp-sa'))

  predict = dsl.ContainerOp(
     name='predict',
     image='google/cloud-sdk:216.0.0',
     command=['sh', '-c'],
     arguments=['''echo %s;
                   echo %s;
                   echo %s;
                   echo "scored_holdout" > /tmp/scored_holdout
                ''' % (train.output, transform_and_split.outputs['holdout_uri'], transform_and_split.outputs['pre_proc_fn_uri'])],
     file_outputs={'scored_holdout': '/tmp/scored_holdout'}).apply(gcp.use_gcp_secret('user-gcp-sa'))

  evaluate = dsl.ContainerOp(
     name='evaluate',
     image='google/cloud-sdk:216.0.0',
     command=['sh', '-c'],
     arguments=['''echo %s
                ''' % predict.outputs['scored_holdout']]).apply(gcp.use_gcp_secret('user-gcp-sa'))


if __name__ == '__main__':
  import kfp.compiler as compiler
  compiler.Compiler().compile(immediate_value_pipeline, 'hackathon.zip')
