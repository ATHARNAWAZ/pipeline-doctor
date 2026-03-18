import { create } from 'zustand';
import type { GraphData, DbtModel, PipelineStatus, AnalysisResult } from '../types';

interface PipelineState {
  graphData: GraphData | null;
  selectedModel: DbtModel | null;
  pipelineStatus: PipelineStatus | null;
  analysisResult: AnalysisResult | null;
  analysisId: string | null;
  isAnalyzing: boolean;

  setGraphData: (data: GraphData | null) => void;
  setSelectedModel: (model: DbtModel | null) => void;
  setPipelineStatus: (status: PipelineStatus | null) => void;
  setAnalysisResult: (result: AnalysisResult | null) => void;
  setAnalysisId: (id: string | null) => void;
  setAnalyzing: (analyzing: boolean) => void;
}

export const usePipelineStore = create<PipelineState>((set) => ({
  graphData: null,
  selectedModel: null,
  pipelineStatus: null,
  analysisResult: null,
  analysisId: null,
  isAnalyzing: false,

  setGraphData: (data) => set({ graphData: data }),
  setSelectedModel: (model) => set({ selectedModel: model }),
  setPipelineStatus: (status) => set({ pipelineStatus: status }),
  setAnalysisResult: (result) => set({ analysisResult: result }),
  setAnalysisId: (id) => set({ analysisId: id }),
  setAnalyzing: (analyzing) => set({ isAnalyzing: analyzing }),
}));
