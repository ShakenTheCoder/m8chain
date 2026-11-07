import VideoAnalyzer from "../../components/video-analyzer";

export default async function SavedAnalysis({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <VideoAnalyzer key={id} analysisId={id} />;
}
