import type { HomeAssistantLike } from "../types/home-assistant";
import {
  API_VERSION,
  type ActivityResponse,
  type ConfigurationResponse,
  type EntryDashboardData,
  type NarrativeResponse,
  type ObservationStatusResponse,
  type ScheduleDocument,
  type ScheduleGetResponse,
  type SchedulePreviewResponse,
  type ScheduleSaveResponse,
  type ScheduleValidationResponse,
  type ShadowStatusResponse,
  type SnapshotResponse,
  type TodayTimelineResponse,
  type ZeroCommandOperatingMode,
} from "../types/contracts";
import {
  validateActivity,
  validateConfiguration,
  validateNarrative,
  validateObservationStatus,
  validateScheduleGet,
  validateSchedulePreview,
  validateScheduleSave,
  validateScheduleValidation,
  validateShadowStatus,
  validateSnapshot,
  validateTodayTimeline,
} from "./validate";

type Validator<T> = (value: unknown) => T;

export class IntelligentClimateClient {
  public constructor(
    private readonly hass: HomeAssistantLike,
    public readonly entryId: string,
  ) {
    if (entryId.length === 0) {
      throw new Error("entryId is required");
    }
  }

  private async request<T>(
    type: string,
    validate: Validator<T>,
    extra: Record<string, unknown> = {},
  ): Promise<T> {
    const response: unknown = await this.hass.callWS({
      type,
      api_version: API_VERSION,
      entry_id: this.entryId,
      ...extra,
    });
    return validate(response);
  }

  public configuration(): Promise<ConfigurationResponse> {
    return this.request(
      "intelligent_climate/config/get",
      validateConfiguration,
    );
  }

  public snapshot(): Promise<SnapshotResponse> {
    return this.request("intelligent_climate/snapshot/get", validateSnapshot);
  }

  public activity(
    offset = 0,
    limit = 100,
    order: "newest" | "oldest" = "newest",
  ): Promise<ActivityResponse> {
    return this.request("intelligent_climate/activity/list", validateActivity, {
      offset,
      limit,
      order,
    });
  }

  public shadowStatus(): Promise<ShadowStatusResponse> {
    return this.request(
      "intelligent_climate/shadow/status",
      validateShadowStatus,
    );
  }

  public observationStatus(): Promise<ObservationStatusResponse> {
    return this.request(
      "intelligent_climate/observation/status",
      validateObservationStatus,
    );
  }

  public todayTimeline(zoneId: string): Promise<TodayTimelineResponse> {
    return this.request(
      "intelligent_climate/timeline/today",
      validateTodayTimeline,
      { zone_id: zoneId },
    );
  }

  public narrative(zoneId: string): Promise<NarrativeResponse> {
    return this.request(
      "intelligent_climate/narrative/current",
      validateNarrative,
      { zone_id: zoneId },
    );
  }

  public schedule(): Promise<ScheduleGetResponse> {
    return this.request(
      "intelligent_climate/schedule/get",
      validateScheduleGet,
    );
  }

  public validateSchedule(
    schedule: ScheduleDocument,
  ): Promise<ScheduleValidationResponse> {
    return this.request(
      "intelligent_climate/schedule/validate",
      validateScheduleValidation,
      { schedule },
    );
  }

  public previewSchedule(
    schedule: ScheduleDocument,
    atUtc?: string,
  ): Promise<SchedulePreviewResponse> {
    return this.request(
      "intelligent_climate/schedule/preview",
      validateSchedulePreview,
      atUtc === undefined ? { schedule } : { schedule, at_utc: atUtc },
    );
  }

  public saveSchedule(
    schedule: ScheduleDocument,
    expectedRevision: number,
  ): Promise<ScheduleSaveResponse> {
    return this.request(
      "intelligent_climate/schedule/save",
      validateScheduleSave,
      { schedule, expected_revision: expectedRevision },
    );
  }

  public setOperatingMode(mode: ZeroCommandOperatingMode): Promise<void> {
    return this.hass.callService("intelligent_climate", "set_operating_mode", {
      entry_id: this.entryId,
      mode,
    });
  }

  public async dashboardData(): Promise<EntryDashboardData> {
    const [configuration, snapshot, activity, shadow, observation] =
      await Promise.all([
        this.configuration(),
        this.snapshot(),
        this.activity(),
        this.shadowStatus(),
        this.observationStatus(),
      ]);
    return { configuration, snapshot, activity, shadow, observation };
  }

  public async subscribe(
    callback: (snapshot: SnapshotResponse) => void,
  ): Promise<() => void> {
    return this.hass.connection.subscribeMessage(
      (message) => callback(validateSnapshot(message)),
      {
        type: "intelligent_climate/subscribe",
        api_version: API_VERSION,
        entry_id: this.entryId,
      },
    );
  }
}
